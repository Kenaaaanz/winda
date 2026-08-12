from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget
from django.forms import modelformset_factory
from .models import Property, PropertyDocument, Unit


class PropertyForm(forms.ModelForm):
    """Form for creating and editing properties"""
    
    class Meta:
        model = Property
        fields = [
            'title', 'description', 'property_type', 'furnishing_status',
            'address', 'city', 'state', 'postal_code',
            'rental_price', 'service_charge', 'security_deposit', 'negotiation_allowed',
            'bedrooms', 'bathrooms', 'parking_spaces', 'square_feet',
            'floor_number', 'total_floors', 'year_built', 'total_units',
            'amenities', 'features',
        ]
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 5,
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'amenities': forms.CheckboxSelectMultiple(),
            'features': forms.CheckboxSelectMultiple(),
            'title': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'address': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'city': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'state': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'rental_price': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'step': '1000',
                'min': '0'
            }),
            'service_charge': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'step': '1000',
                'min': '0'
            }),
            'security_deposit': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'step': '1000',
                'min': '0'
            }),
            'bedrooms': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'min': '0'
            }),
            'bathrooms': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'min': '0'
            }),
            'parking_spaces': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'min': '0'
            }),
            'square_feet': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'min': '0'
            }),
            'floor_number': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'min': '0'
            }),
            'total_floors': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'min': '0'
            }),
            'year_built': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'min': '1900',
                'max': '2100'
            }),
            'total_units': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'min': '1'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set up amenities and features choices
        from .services import PropertyService
        self.fields['amenities'].choices = [(a, a) for a in PropertyService.get_amenities_list()]
        self.fields['features'].choices = [(f, f) for f in PropertyService.get_features_list()]
        
        # Make fields not required where appropriate
        self.fields['service_charge'].required = False
        self.fields['security_deposit'].required = False
        self.fields['square_feet'].required = False
        self.fields['floor_number'].required = False
        self.fields['total_floors'].required = False
        self.fields['year_built'].required = False
        self.fields['postal_code'].required = False
        self.fields['amenities'].required = False
        self.fields['features'].required = False
        self.fields['total_units'].required = False

    def clean_total_units(self):
        total_units = self.cleaned_data['total_units'] or 1
        if self.instance.pk and total_units < self.instance.occupied_units:
            raise forms.ValidationError(
                f'Units cannot be fewer than the {self.instance.occupied_units} unit(s) with an active or pending lease.'
            )
        return total_units

    def clean_amenities(self):
        return self.cleaned_data.get('amenities') or []

    def clean_features(self):
        return self.cleaned_data.get('features') or []


class PropertySearchForm(forms.Form):
    """Form for searching properties"""
    search_text = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'placeholder': 'Search by title, location...',
        'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
    }))
    city = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'placeholder': 'City or area',
        'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
    }))
    property_type = forms.ChoiceField(required=False, choices=[('', 'All Types')])
    min_price = forms.DecimalField(required=False, min_value=0, widget=forms.NumberInput(attrs={
        'placeholder': 'Min',
        'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
    }))
    max_price = forms.DecimalField(required=False, min_value=0, widget=forms.NumberInput(attrs={
        'placeholder': 'Max',
        'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
    }))
    bedrooms = forms.ChoiceField(required=False, choices=[('', 'Any')])
    amenities = forms.MultipleChoiceField(required=False, widget=forms.CheckboxSelectMultiple())
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Property
        self.fields['property_type'].choices = [('', 'All Types')] + list(Property.PROPERTY_TYPES)
        self.fields['bedrooms'].choices = [('', 'Any')] + [(i, f'{i}+') for i in range(1, 6)]
        from .services import PropertyService
        self.fields['amenities'].choices = [(a, a) for a in PropertyService.get_amenities_list()]


class PropertyDocumentForm(forms.ModelForm):
    """Form for uploading property documents"""
    
    class Meta:
        model = PropertyDocument
        fields = ['document_type', 'document', 'description']
        widgets = {
            'document_type': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'document': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Optional description'
            }),
        }

from django import forms
from django.forms import modelformset_factory
from .models import Property, Unit

class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = [
            'unit_number', 'floor_number', 'bedrooms', 'bathrooms', 
            'square_feet', 'rental_price', 'service_charge', 'security_deposit',
            'amenities', 'features', 'status'
        ]
        widgets = {
            'unit_number': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'e.g., A1, 101'
            }),
            'floor_number': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'bedrooms': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'min': 0
            }),
            'bathrooms': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'min': 0
            }),
            'square_feet': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'min': 0
            }),
            'rental_price': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'step': '1000'
            }),
            'service_charge': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'step': '100'
            }),
            'security_deposit': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'step': '1000'
            }),
            'amenities': forms.SelectMultiple(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'features': forms.SelectMultiple(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set up amenities and features choices
        from .services import PropertyService
        amenities_choices = [(a, a) for a in PropertyService.get_amenities_list()]
        features_choices = [(f, f) for f in PropertyService.get_features_list()]
        self.fields['amenities'].choices = amenities_choices
        self.fields['features'].choices = features_choices
        
        # Make amenities and features optional with default empty list
        self.fields['amenities'].required = False
        self.fields['features'].required = False
        
        # Set initial values if instance exists
        if self.instance and self.instance.pk:
            if self.instance.amenities:
                self.fields['amenities'].initial = self.instance.amenities
            if self.instance.features:
                self.fields['features'].initial = self.instance.features
    
    def clean_amenities(self):
        """Ensure amenities is a list, not None"""
        amenities = self.cleaned_data.get('amenities', [])
        return amenities if amenities is not None else []
    
    def clean_features(self):
        """Ensure features is a list, not None"""
        features = self.cleaned_data.get('features', [])
        return features if features is not None else []


# Create a formset for multiple units
UnitFormSet = modelformset_factory(
    Unit,
    form=UnitForm,
    fields=['unit_number', 'floor_number', 'bedrooms', 'bathrooms', 
            'square_feet', 'rental_price', 'service_charge', 'security_deposit',
            'amenities', 'features', 'status'],
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


class PropertyWithUnitsForm(forms.ModelForm):
    """Enhanced property form with multi-unit support"""
    
    class Meta:
        model = Property
        fields = [
            'title', 'description', 'property_type', 'furnishing_status',
            'address', 'city', 'state', 'postal_code',
            'rental_price', 'service_charge', 'security_deposit', 'negotiation_allowed',
            'bedrooms', 'bathrooms', 'parking_spaces', 'square_feet',
            'floor_number', 'total_floors', 'year_built',
            'main_image', 'is_multi_unit', 'total_units'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5, 'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'title': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'address': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'city': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'state': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'postal_code': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'rental_price': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500', 'step': '1000'}),
            'service_charge': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500', 'step': '100'}),
            'security_deposit': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500', 'step': '1000'}),
            'bedrooms': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500', 'min': 0}),
            'bathrooms': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500', 'min': 0}),
            'parking_spaces': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500', 'min': 0}),
            'square_feet': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500', 'min': 0}),
            'floor_number': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500', 'min': 0}),
            'total_floors': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500', 'min': 0}),
            'year_built': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500', 'min': 1900, 'max': 2100}),
            'total_units': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500', 'min': 1}),
            'is_multi_unit': forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'}),
            'negotiation_allowed': forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'}),
            'main_image': forms.FileInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
        }
        
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
       