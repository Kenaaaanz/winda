from decimal import Decimal, ROUND_HALF_UP, localcontext

from django.db.models import Q

from .models import UtilityReading, UtilityTariff


CENT = Decimal('0.01')


def tariff_for_reading(device, recorded_at):
    return UtilityTariff.objects.filter(
        utility=device.utility,
        provider=device.provider,
        effective_from__lte=recorded_at,
    ).filter(
        Q(effective_until__isnull=True) | Q(effective_until__gt=recorded_at)
    ).order_by('-effective_from').first()


def price_reading(usage_delta, tariff):
    if tariff is None:
        return None
    with localcontext() as context:
        context.prec = 40
        return (usage_delta * tariff.rate_per_unit).quantize(
            CENT,
            rounding=ROUND_HALF_UP,
        )


def device_summary(device):
    readings = list(device.readings.order_by('recorded_at'))
    total_usage = sum((reading.usage_delta for reading in readings), Decimal('0'))
    priced_readings = [
        reading for reading in readings if reading.estimated_cost is not None
    ]
    total_cost = sum(
        (reading.estimated_cost for reading in priced_readings),
        Decimal('0'),
    )
    unpriced_usage = sum(
        (
            reading.usage_delta
            for reading in readings
            if reading.estimated_cost is None
        ),
        Decimal('0'),
    )
    return {
        'device': device,
        'latest_reading': readings[-1] if readings else None,
        'total_usage': total_usage,
        'estimated_cost': total_cost,
        'unpriced_usage': unpriced_usage,
    }


def owner_utility_summary(owner):
    devices = owner.properties.prefetch_related('utility_devices__readings')
    return [
        device_summary(device)
        for property_obj in devices
        for device in property_obj.utility_devices.all()
    ]
