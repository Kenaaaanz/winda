import cloudinary.api
from django.db import transaction

from apps.analytics.models import AnalyticsEvent
from apps.accounts.models import User
from apps.properties.models import Property
from apps.payments.models import ScoutPayout


def _delete_cloudinary_assets(user_id, property_ids):
    prefixes = [
        f'profiles/{user_id}',
        f'business_licenses/{user_id}',
    ]
    prefixes.extend(f'properties/{property_id}' for property_id in property_ids)

    for prefix in prefixes:
        for resource_type in ('image', 'video', 'raw'):
            cloudinary.api.delete_resources_by_prefix(
                prefix,
                resource_type=resource_type,
            )


@transaction.atomic
def erase_user_account(user):
    account_id = user.pk
    property_ids = list(
        Property.objects.filter(owner__user_id=account_id).values_list('id', flat=True)
    )
    email = user.email
    full_name = user.get_full_name() or user.email

    ScoutPayout.objects.filter(scout=user).update(
        paystack_response={},
        transfer_code='',
    )
    Property.objects.filter(owner__user_id=account_id).delete()
    AnalyticsEvent.objects.filter(user_id=account_id).delete()
    user.delete()
    transaction.on_commit(
        lambda: _delete_cloudinary_assets(account_id, property_ids)
    )
    return {'email': email, 'full_name': full_name}
