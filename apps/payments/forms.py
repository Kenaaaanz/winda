from django import forms
from django.utils import timezone
from .models import Payment, SubscriptionPlan


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['payment_type', 'amount', 'description', 'property', 'due_date']
        widgets = {
            'payment_type': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'step': '100',
                'min': '0'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'rows': 3,
                'placeholder': 'Payment description...'
            }),
            'property': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'due_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        from apps.properties.models import Property

        # Do not let a tenant initiate a payment against an unrelated listing.
        # Owners retain access to their own properties for owner-created charges.
        if user and getattr(user, 'is_owner', False):
            self.fields['property'].queryset = Property.objects.filter(owner=user.owner_profile)
        elif user:
            self.fields['property'].queryset = Property.objects.filter(
                leases__tenant=user,
                leases__status__in=['PENDING_SIGNATURE', 'ACTIVE'],
            ).distinct()
        else:
            self.fields['property'].queryset = Property.objects.none()
        self.fields['due_date'].initial = timezone.now().date() + timezone.timedelta(days=30)
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero.')
        return amount


class SubscriptionForm(forms.Form):
    plan_id = forms.IntegerField(widget=forms.HiddenInput())
    period = forms.ChoiceField(
        choices=[
            ('monthly', 'Monthly'),
            ('yearly', 'Yearly (Save 20%)')
        ],
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
        })
    )
    
    def clean_plan_id(self):
        plan_id = self.cleaned_data.get('plan_id')
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
            return plan.id
        except SubscriptionPlan.DoesNotExist:
            raise forms.ValidationError('Invalid subscription plan selected.')
