# apps/tenants/forms.py
from django import forms
from .models import TenantApplication, Lease

from django import forms
from .models import TenantApplication
from apps.properties.models import Unit

class TenantApplicationForm(forms.ModelForm):
    unit = forms.ModelChoiceField(
        queryset=Unit.objects.none(),
        required=False,
        label='Select Unit',
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
        })
    )
    
    class Meta:
        model = TenantApplication
        fields = [
            'unit', 'intended_move_in_date', 'preferred_lease_duration',
            'monthly_income', 'employment_status',
        ]
        widgets = {
            'intended_move_in_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'preferred_lease_duration': forms.NumberInput(attrs={
                'min': 1,
                'max': 60,
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'monthly_income': forms.NumberInput(attrs={
                'min': 0,
                'step': 1000,
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'employment_status': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'e.g., Employed, Self-Employed, Student'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        property_obj = kwargs.pop('property_obj', None)
        super().__init__(*args, **kwargs)
        
        if property_obj:
            # Show only available units for this property
            self.fields['unit'].queryset = property_obj.units.filter(
                is_available=True,
                status='AVAILABLE'
            ).order_by('unit_number')  # Order by unit number
            
            # Add unit labels with details
            self.fields['unit'].label_from_instance = lambda obj: f"Unit {obj.unit_number} - {obj.bedrooms}br/{obj.bathrooms}ba - KES {obj.get_rental_price():,}"
            
            # If only one unit available, select it by default
            if self.fields['unit'].queryset.count() == 1:
                self.fields['unit'].initial = self.fields['unit'].queryset.first()
            
            # Make unit required if property is multi-unit
            if property_obj.is_multi_unit:
                self.fields['unit'].required = True
                self.fields['unit'].empty_label = "Select a unit"
            else:
                self.fields['unit'].widget = forms.HiddenInput()
                self.fields['unit'].required = False
        
        self.fields['intended_move_in_date'].required = True
        self.fields['preferred_lease_duration'].required = True
        self.fields['monthly_income'].required = True

class LeaseForm(forms.ModelForm):
    class Meta:
        model = Lease
        fields = [
            'start_date', 'end_date', 
            'termination_notice_period',
            'late_payment_penalty', 'lease_agreement'
        ]
        
        widgets = {
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'termination_notice_period': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'min': 0
            }),
            'late_payment_penalty': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'step': '100'
            }),
            'lease_agreement': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
        }