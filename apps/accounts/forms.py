from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.core.validators import RegexValidator
from django.contrib.auth import get_user_model

from apps.properties.models import Property
from .models import CaretakerProfile, User, UserProfile, OwnerProfile, TenantProfile, PaystackSubaccount

User = get_user_model()

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm',
        'placeholder': 'Email address'
    }))
    first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': 'appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm',
        'placeholder': 'First Name'
    }))
    last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': 'appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm',
        'placeholder': 'Last Name'
    }))
    phone = forms.CharField(
        max_length=15,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 'Enter a valid phone number.')],
        widget=forms.TextInput(attrs={
            'class': 'appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm',
            'placeholder': 'Phone Number'
        })
    )
    user_type = forms.ChoiceField(
        choices=User.USER_TYPES,
        widget=forms.Select(attrs={
            'class': 'appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm'
        })
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm',
            'placeholder': 'Password'
        })
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm',
            'placeholder': 'Confirm Password'
        })
    )

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone', 'user_type', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']  # Use email as username
        if commit:
            user.save()
            # Create profile based on user type
            UserProfile.objects.get_or_create(user=user)
            if user.user_type == 'HOUSE_OWNER':
                OwnerProfile.objects.get_or_create(user=user)
            elif user.user_type == 'TENANT':
                TenantProfile.objects.get_or_create(user=user)
        return user


class UserLoginForm(AuthenticationForm):
    username = forms.EmailField(label='Email', widget=forms.EmailInput(attrs={
        'class': 'appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm',
        'placeholder': 'Email address'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm',
        'placeholder': 'Password'
    }))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'placeholder': 'Enter your email'})
        self.fields['password'].widget.attrs.update({'placeholder': 'Enter your password'})


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'address', 'city', 'country', 'postal_code',
            'business_name', 'business_registration', 'tax_id',
            'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relation',
            'preferred_contact_method', 'marketing_opt_in'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'business_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'business_registration': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'tax_id': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'city': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'country': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'postal_code': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'preferred_contact_method': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
        }


class OwnerProfileForm(forms.ModelForm):
    """Form for updating owner profile"""
    class Meta:
        model = OwnerProfile
        fields = [
            'company_name', 'company_registration_number', 'tax_pin',
            'business_license'
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'company_registration_number': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'tax_pin': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'business_license': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
        }


class TenantProfileForm(forms.ModelForm):
    """Form for updating tenant profile"""
    class Meta:
        model = TenantProfile
        fields = [
            'employer_name', 'employer_contact', 'job_title', 'monthly_income',
            'guarantor_name', 'guarantor_phone', 'guarantor_email', 'guarantor_relationship',
            'previous_rental_address', 'previous_landlord_name', 'previous_landlord_phone',
            'previous_rental_duration', 'reference_name', 'reference_phone', 'reference_email'
        ]
        widgets = {
            'employer_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'employer_contact': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'job_title': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'monthly_income': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'guarantor_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'guarantor_phone': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'guarantor_email': forms.EmailInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'guarantor_relationship': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'previous_rental_address': forms.Textarea(attrs={'rows': 2, 'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'reference_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'reference_phone': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'reference_email': forms.EmailInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
        }


class UserUpdateForm(forms.ModelForm):
    """Form for updating user basic info"""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'bio', 'profile_picture']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'phone': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'bio': forms.Textarea(attrs={'rows': 3, 'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
            'profile_picture': forms.FileInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'}),
        }


class CustomPasswordChangeForm(PasswordChangeForm):
    """Custom password change form"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            })


class PasswordResetForm(forms.Form):
    """Password reset form"""
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'appearance-none rounded-md relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm',
        'placeholder': 'Email address'
    }))

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError('No user found with this email address.')
        return email



class PaystackSubaccountForm(forms.ModelForm):
    """Form for setting up Paystack subaccount for bank account information"""
    
    # Kenyan Bank Codes
    BANK_CHOICES = [
        ('', 'Select Bank'),
        ('001', 'KCB Bank Kenya'),
        ('002', 'Equity Bank Kenya'),
        ('003', 'Co-operative Bank of Kenya'),
        ('004', 'Barclays Bank Kenya'),
        ('005', 'Standard Chartered Bank Kenya'),
        ('006', 'Absa Bank Kenya'),
        ('007', 'Diamond Trust Bank (DTB)'),
        ('008', 'I&M Bank Kenya'),
        ('009', 'NCBA Bank Kenya'),
        ('010', 'Stanbic Bank Kenya'),
        ('011', 'Sidian Bank'),
        ('012', 'Ecobank Kenya'),
        ('013', 'HFC Bank Kenya'),
        ('014', 'Habib Bank Kenya'),
        ('015', 'Bank of Africa Kenya'),
        ('016', 'Citibank Kenya'),
        ('017', 'Fidelity Commercial Bank'),
        ('018', 'Prime Bank Kenya'),
        ('019', 'African Banking Corporation (ABC)'),
        ('020', 'Guardian Bank'),
        ('021', 'Vijana Bank'),
        ('022', 'Middle East Bank Kenya'),
        ('023', 'Development Bank of Kenya'),
        ('024', 'Spire Bank Kenya'),
        ('025', 'Dubai Islamic Bank Kenya'),
        ('026', 'Gulf African Bank'),
        ('027', 'First Community Bank'),
        ('028', 'SBM Bank Kenya'),
        ('029', 'Kingdom Bank'),
        ('030', 'Credit Bank Kenya'),
        ('031', 'Consolidated Bank'),
        ('032', 'UBA Kenya'),
        ('033', 'Bank of India Kenya'),
        ('034', 'M Oriental Bank'),
        ('035', 'K-Rep Bank'),
        ('036', 'HF Group'),
        ('037', 'Mwalimu National Sacco'),
        ('038', 'Harambee Sacco'),
        ('039', 'Stima Sacco'),
        ('040', 'Kenya Police Sacco'),
        ('041', 'Teachers Sacco'),
        ('042', 'Mombasa Maize Millers Sacco'),
        ('043', 'Kenya Tea Development Agency'),
        ('044', 'M-pesa Paybill'),
        ('045', 'Safaricom M-Pesa'),
        ('046', 'Airtel Money'),
        ('047', 'Telkom Money'),
        ('048', 'Paypal Kenya'),
        ('049', 'Pesapal'),
        ('050', 'Jambo Pay'),
        ('051', 'Cellulant'),
    ]
    
    bank_code = forms.ChoiceField(
        choices=BANK_CHOICES,
        label='Bank Name',
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
        })
    )
    
    account_number = forms.CharField(
        label='Account Number',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Enter your account number (e.g., 1234567890)',
            'maxlength': '20',
        })
    )
    
    account_name = forms.CharField(
        label='Account Holder Name',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Enter the account holder name'
        })
    )
    
    business_name = forms.CharField(
        label='Business/Company Name',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Enter your business or company name'
        })
    )
    
    class Meta:
        model = PaystackSubaccount
        fields = ['bank_code', 'account_number', 'account_name', 'business_name']
    
    def clean_account_number(self):
        account_number = self.cleaned_data.get('account_number')
        if not account_number:
            raise forms.ValidationError('Account number is required.')
        
        # Remove any spaces or special characters
        account_number = ''.join(filter(str.isdigit, account_number))
        
        if len(account_number) < 10:
            raise forms.ValidationError('Account number must be at least 10 digits.')
        
        if len(account_number) > 20:
            raise forms.ValidationError('Account number must not exceed 20 digits.')
        
        return account_number
    
    def clean_bank_code(self):
        bank_code = self.cleaned_data.get('bank_code')
        if not bank_code:
            raise forms.ValidationError('Please select a bank.')
        return bank_code

    def __init__(self, *args, bank_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        if bank_choices is not None:
            self.fields['bank_code'].choices = [('', 'Select Bank')] + bank_choices

class CaretakerInviteForm(forms.Form):
    """Form to invite a caretaker"""
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Enter caretaker email'
        })
    )
    permission_level = forms.ChoiceField(
        choices=CaretakerProfile.PERMISSION_LEVELS,
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
        })
    )
    assigned_properties = forms.ModelMultipleChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
        }),
        label='Assigned Properties'
    )
    
    def __init__(self, *args, **kwargs):
        owner = kwargs.pop('owner', None)
        super().__init__(*args, **kwargs)
        if owner:
            from apps.properties.models import Property
            self.fields['assigned_properties'].queryset = Property.objects.filter(owner=owner)


class CaretakerUpdateForm(forms.ModelForm):
    """Form to update caretaker permissions"""
    
    assigned_properties = forms.ModelMultipleChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
        })
    )
    
    class Meta:
        model = CaretakerProfile
        fields = ['permission_level', 'is_active']
        widgets = {
            'permission_level': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            })
        }
    
    def __init__(self, *args, **kwargs):
        owner = kwargs.pop('owner', None)
        super().__init__(*args, **kwargs)
        if owner:
            from apps.properties.models import Property
            self.fields['assigned_properties'].queryset = Property.objects.filter(owner=owner)
