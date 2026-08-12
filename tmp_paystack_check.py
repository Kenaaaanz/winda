import os
import json
import django
import paystack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'winda.settings')
django.setup()

from django.conf import settings

paystack.api_key = settings.PAYSTACK_SECRET_KEY

try:
    response = paystack.Transaction.initialize(
        email='test@example.com',
        amount=10000,
        reference='TEST-123',
        metadata={'payment_type': 'RENT'}
    )
    print(json.dumps(response, indent=2))
except Exception as exc:
    import traceback
    traceback.print_exc()
