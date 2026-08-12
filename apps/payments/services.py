from datetime import timezone

import requests
from django.conf import settings
from decimal import Decimal


class PaystackService:
    BASE_URL = 'https://api.paystack.co'

    def __init__(self):
        self.secret_key = settings.PAYSTACK_SECRET_KEY

    def _request(self, method, path, **kwargs):
        headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json',
        }
        response = requests.request(
            method,
            f'{self.BASE_URL}{path}',
            headers=headers,
            timeout=30,
            **kwargs,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {'status': False, 'message': response.text}

        if response.status_code >= 400:
            return {
                'status': False,
                'message': payload.get('message', 'Paystack request failed'),
                'payload': payload,
            }

        if isinstance(payload, dict) and payload.get('status') is False:
            return {
                'status': False,
                'message': payload.get('message', 'Paystack request failed'),
                'payload': payload,
            }

        return payload

    def initialize_transaction(self, email, amount, reference, metadata=None):
        """Initialize a Paystack transaction."""
        try:
            payload = {
                'email': email,
                'amount': int(amount),
                'reference': reference,
                'metadata': metadata or {},
            }
            return self._request('post', '/transaction/initialize', json=payload)
        except Exception as exc:
            return {'status': False, 'message': str(exc)}

    def verify_transaction(self, reference):
        """Verify a Paystack transaction."""
        try:
            return self._request('get', f'/transaction/verify/{reference}')
        except Exception as exc:
            return {'status': False, 'message': str(exc)}

    def create_plan(self, name, amount, interval='monthly'):
        """Create a subscription plan."""
        try:
            payload = {'name': name, 'amount': int(amount), 'interval': interval}
            return self._request('post', '/plan', json=payload)
        except Exception as exc:
            return {'status': False, 'message': str(exc)}

    def create_subscription(self, customer_email, plan_code, authorization_code=None):
        """Create a subscription."""
        try:
            payload = {
                'customer': customer_email,
                'plan': plan_code,
                'authorization': authorization_code,
            }
            return self._request('post', '/subscription', json=payload)
        except Exception as exc:
            return {'status': False, 'message': str(exc)}
    
    def create_subaccount(self, business_name, settlement_bank, account_number, account_holder_name, percentage_charge=3):
        """Create a Paystack subaccount for an owner to receive payments.
        
        Args:
            business_name: Name of the business/owner
            settlement_bank: Bank code (e.g., '001' for Zenith Bank)
            account_number: Bank account number
            account_holder_name: Name on the bank account
            percentage_charge: Percentage to charge to the subaccount (Winda's cut, default 3%)
        
        Returns:
            Response from Paystack with subaccount_code
        """
        try:
            payload = {
                'business_name': business_name,
                'settlement_bank': settlement_bank,
                'account_number': account_number,
                'account_holder_name': account_holder_name,
                'percentage_charge': percentage_charge,
            }
            return self._request('post', '/subaccount', json=payload)
        except Exception as exc:
            return {'status': False, 'message': str(exc)}
    
    def get_subaccount(self, subaccount_code):
        """Get details of a subaccount."""
        try:
            return self._request('get', f'/subaccount/{subaccount_code}')
        except Exception as exc:
            return {'status': False, 'message': str(exc)}
    
    def update_subaccount(self, subaccount_code, business_name=None, settlement_bank=None, 
                         account_number=None, account_holder_name=None, percentage_charge=None):
        """Update a subaccount."""
        try:
            payload = {}
            if business_name:
                payload['business_name'] = business_name
            if settlement_bank:
                payload['settlement_bank'] = settlement_bank
            if account_number:
                payload['account_number'] = account_number
            if account_holder_name:
                payload['account_holder_name'] = account_holder_name
            if percentage_charge is not None:
                payload['percentage_charge'] = percentage_charge
            
            return self._request('put', f'/subaccount/{subaccount_code}', json=payload)
        except Exception as exc:
            return {'status': False, 'message': str(exc)}
    
    def list_subaccounts(self):
        """List all subaccounts."""
        try:
            return self._request('get', '/subaccount')
        except Exception as exc:
            return {'status': False, 'message': str(exc)}

    def list_banks(self, country='kenya'):
        """Return Paystack's current bank codes for a supported country."""
        try:
            return self._request('get', '/bank', params={'country': country, 'perPage': 100})
        except Exception as exc:
            return {'status': False, 'message': str(exc)}
    
    def initialize_transaction_with_subaccount(self, email, amount, reference, subaccount_code, metadata=None):
        """Initialize a transaction to be settled to a subaccount.
        
        Args:
            email: Customer email
            amount: Amount in kobo (for Paystack)
            reference: Unique reference for transaction
            subaccount_code: Paystack subaccount code to receive settlement
            metadata: Additional metadata
        
        Returns:
            Response from Paystack with authorization_url
        """
        try:
            payload = {
                'email': email,
                'amount': int(amount),
                'reference': reference,
                'subaccount': subaccount_code,
                'metadata': metadata or {},
            }
            return self._request('post', '/transaction/initialize', json=payload)
        except Exception as exc:
            return {'status': False, 'message': str(exc)}

class PaymentService:
    PLATFORM_FEE_PERCENT = Decimal('3.00')  # 3% to Winda, 97% to owner
    
    @staticmethod
    def calculate_fee_split(amount, platform_fee_percent=None):
        """Calculate the platform fee split: 3% to Winda, 97% to owner.
        
        Args:
            amount: The total payment amount
            platform_fee_percent: Percentage fee (default 3%)
        
        Returns:
            Dictionary with platform_fee and owner_amount
        """
        if platform_fee_percent is None:
            platform_fee_percent = PaymentService.PLATFORM_FEE_PERCENT
        
        platform_fee = (amount * platform_fee_percent / 100).quantize(Decimal('0.01'))
        owner_amount = (amount - platform_fee).quantize(Decimal('0.01'))
        
        return {
            'platform_fee': platform_fee,
            'owner_amount': owner_amount,
            'platform_percentage': platform_fee_percent,
            'owner_percentage': 100 - platform_fee_percent,
        }
    
    @staticmethod
    def calculate_late_fee(payment, days_late):
        """Calculate late fee based on days late"""
        if days_late <= 0:
            return Decimal('0')
        # 5% of amount per month late, prorated by day
        monthly_rate = Decimal('0.05')
        return payment.amount * monthly_rate * (days_late / 30)

    @staticmethod
    def get_property_payment_amount(property_obj, payment_type):
        if payment_type == 'RENT':
            return property_obj.rental_price
        if payment_type == 'SERVICE_CHARGE':
            return property_obj.service_charge
        if payment_type == 'DEPOSIT':
            return property_obj.security_deposit
        return Decimal('0.00')

    @staticmethod
    def generate_invoice_number():
        """Generate unique invoice number"""
        from datetime import datetime
        import random
        return f"INV-{datetime.now().strftime('%Y%m%d')}-{random.randint(10000, 99999)}"
    
    @staticmethod
    def create_invoice_for_payment(payment):
        """Create invoice for a payment if it doesn't exist"""
        from .models import Invoice
        from decimal import Decimal
        
        if hasattr(payment, 'invoice'):
            return payment.invoice
        
        # Check if invoice already exists with this payment
        existing_invoice = Invoice.objects.filter(payment=payment).first()
        if existing_invoice:
            return existing_invoice
        
        invoice = Invoice.objects.create(
            payment=payment,
            user=payment.payer,
            invoice_number=PaymentService.generate_invoice_number(),
            amount=payment.amount,
            tax=Decimal('0'),
            total_amount=payment.amount,
            due_date=payment.due_date or timezone.now() + timezone.timedelta(days=30),
            status='PAID',
            paid_date=timezone.now()
        )
        return invoice
