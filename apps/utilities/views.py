import hashlib
import hmac
import json
import re
import secrets
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.accounts.decorators import owner_required
from apps.accounts.models import OwnerProfile

from .forms import UtilityDeviceForm
from .models import UtilityDevice, UtilityReading
from .services import owner_utility_summary, price_reading, tariff_for_reading


def _api_error(message, status):
    return JsonResponse({'error': message}, status=status)


@login_required
@owner_required
def dashboard(request):
    owner = get_object_or_404(OwnerProfile, user=request.user)
    summaries = owner_utility_summary(owner)
    return render(request, 'utilities/dashboard.html', {
        'summaries': summaries,
        'can_add_device': request.user.verification_status == 'VERIFIED',
    })


@login_required
@owner_required
def register_device(request):
    owner = get_object_or_404(OwnerProfile, user=request.user)
    if request.user.verification_status != 'VERIFIED':
        messages.error(request, 'Your owner account must be verified to register devices.')
        return redirect('utilities:dashboard')

    if request.method == 'POST':
        form = UtilityDeviceForm(request.POST, owner=request.user)
        if form.is_valid():
            token = secrets.token_urlsafe(32)
            device = form.save(commit=False)
            device.api_key_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
            device.full_clean()
            device.save()
            request.session[f'utility_device_token_{device.id}'] = token
            return redirect('utilities:device_created', device_id=device.id)
    else:
        form = UtilityDeviceForm(owner=request.user)

    if not owner.properties.exists():
        messages.info(request, 'Add a property before registering utility devices.')
    return render(request, 'utilities/register_device.html', {'form': form})


@login_required
@owner_required
def device_created(request, device_id):
    owner = get_object_or_404(OwnerProfile, user=request.user)
    device = get_object_or_404(
        UtilityDevice,
        id=device_id,
        property__owner=owner,
    )
    token = request.session.pop(f'utility_device_token_{device.id}', None)
    response = render(request, 'utilities/register_device.html', {
        'form': UtilityDeviceForm(owner=request.user),
        'device': device,
        'device_token': token,
    })
    response['Cache-Control'] = 'no-store'
    return response


@csrf_exempt
@require_POST
def ingest_reading(request, device_id):
    if len(request.body) > 4096:
        return _api_error('Request body is too large.', 413)

    api_key = request.headers.get('X-Device-Key', '')
    timestamp_header = request.headers.get('X-Device-Timestamp', '')
    signature = request.headers.get('X-Device-Signature', '')
    if not api_key or not timestamp_header or not signature:
        return _api_error('Device authentication headers are required.', 401)

    if not re.fullmatch(r'[0-9]{1,12}', timestamp_header):
        return _api_error('Invalid request timestamp.', 401)
    try:
        timestamp = int(timestamp_header)
    except ValueError:
        return _api_error('Invalid request timestamp.', 401)

    now = timezone.now()
    skew_seconds = getattr(settings, 'UTILITY_DEVICE_CLOCK_SKEW_SECONDS', 300)
    if abs(now.timestamp() - timestamp) > skew_seconds:
        return _api_error('Request timestamp is outside the allowed window.', 401)

    expected_signature = hmac.new(
        api_key.encode('utf-8'),
        timestamp_header.encode('ascii') + b'\n' + request.body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, signature.lower()):
        return _api_error('Invalid device signature.', 401)

    token_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _api_error('Request body must be valid JSON.', 400)
    if not isinstance(payload, dict):
        return _api_error('Request body must be a JSON object.', 400)

    external_id = payload.get('external_id')
    if not isinstance(external_id, str) or not external_id.strip() or len(external_id) > 100:
        return _api_error('A non-empty external_id of at most 100 characters is required.', 400)

    try:
        meter_value = Decimal(str(payload.get('meter_value')))
    except (InvalidOperation, TypeError, ValueError):
        return _api_error('meter_value must be a decimal number.', 400)
    if not meter_value.is_finite() or meter_value < 0:
        return _api_error('meter_value must be a finite, non-negative number.', 400)

    recorded_at_raw = payload.get('recorded_at')
    try:
        recorded_at = (
            parse_datetime(recorded_at_raw)
            if isinstance(recorded_at_raw, str)
            else None
        )
    except ValueError:
        recorded_at = None
    if recorded_at is None or timezone.is_naive(recorded_at):
        return _api_error('recorded_at must be an ISO 8601 timestamp with a timezone.', 400)
    if recorded_at > now + timedelta(seconds=skew_seconds):
        return _api_error('recorded_at cannot be in the future.', 400)
    if meter_value >= Decimal('1000000000000000') or meter_value.as_tuple().exponent < -3:
        return _api_error('meter_value must fit the supported 3-decimal meter precision.', 400)

    with transaction.atomic():
        try:
            device = UtilityDevice.objects.select_for_update().get(
                id=device_id,
                is_enabled=True,
            )
        except UtilityDevice.DoesNotExist:
            return _api_error('Unknown or disabled device.', 404)
        if not hmac.compare_digest(device.api_key_hash, token_hash):
            return _api_error('Invalid device credentials.', 401)
        if device.readings.filter(external_id=external_id.strip()).exists():
            return _api_error('This external_id has already been received.', 409)

        latest = device.readings.order_by('-recorded_at').first()
        if latest is None and recorded_at < device.created_at:
            return _api_error('The first reading cannot predate device registration.', 400)
        previous_value = latest.meter_value if latest else device.initial_reading
        if latest and recorded_at <= latest.recorded_at:
            return _api_error('Readings must be newer than the last accepted reading.', 409)
        if meter_value < previous_value:
            return _api_error('Cumulative meter readings cannot decrease.', 400)

        usage_delta = meter_value - previous_value
        tariff = tariff_for_reading(device, recorded_at)
        estimated_cost = price_reading(usage_delta, tariff)
        if estimated_cost is not None and estimated_cost >= Decimal('1000000000000'):
            return _api_error('The estimated reading cost exceeds the supported amount.', 400)
        reading = UtilityReading(
            device=device,
            external_id=external_id.strip(),
            meter_value=meter_value,
            usage_delta=usage_delta,
            recorded_at=recorded_at,
            tariff=tariff,
            rate_applied=tariff.rate_per_unit if tariff else None,
            estimated_cost=estimated_cost,
        )
        try:
            with transaction.atomic():
                reading.save()
        except IntegrityError:
            if device.readings.filter(external_id=external_id.strip()).exists():
                return _api_error('This external_id has already been received.', 409)
            raise

    return JsonResponse({
        'id': str(reading.id),
        'external_id': reading.external_id,
        'usage_delta': str(reading.usage_delta),
        'unit': device.unit_of_measure,
        'rate_applied': str(reading.rate_applied) if reading.rate_applied is not None else None,
        'estimated_cost_kes': str(reading.estimated_cost) if reading.estimated_cost is not None else None,
    }, status=201)
