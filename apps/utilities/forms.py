from django import forms

from apps.properties.models import Property, Unit

from .models import UtilityDevice, UtilityTariff


class UtilityDeviceForm(forms.ModelForm):
    class Meta:
        model = UtilityDevice
        fields = (
            'property',
            'unit',
            'name',
            'utility',
            'provider',
            'initial_reading',
        )
        widgets = {
            'initial_reading': forms.NumberInput(attrs={'step': '0.001', 'min': '0'}),
        }

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['property'].queryset = Property.objects.filter(
            owner=owner.owner_profile
        ).order_by('title')
        self.fields['unit'].queryset = Unit.objects.filter(
            property_obj__owner=owner.owner_profile
        ).order_by('property_obj__title', 'unit_number')

        utility = self.data.get('utility') or self.initial.get('utility')
        providers = UtilityTariff.objects.all()
        if utility:
            providers = providers.filter(utility=utility)
        provider_names = providers.order_by('provider').values_list(
            'provider', flat=True
        ).distinct()
        self.fields['provider'].choices = [
            ('', 'Select a configured tariff provider'),
            *((name, name) for name in provider_names),
        ]

    def clean(self):
        cleaned_data = super().clean()
        property_obj = cleaned_data.get('property')
        unit = cleaned_data.get('unit')
        utility = cleaned_data.get('utility')
        provider = cleaned_data.get('provider')

        if property_obj and unit and unit.property_obj_id != property_obj.id:
            self.add_error('unit', 'Select a unit belonging to the chosen property.')
        if utility and provider and not UtilityTariff.objects.filter(
            utility=utility,
            provider=provider,
        ).exists():
            self.add_error('provider', 'Select a provider with a configured tariff.')
        return cleaned_data
