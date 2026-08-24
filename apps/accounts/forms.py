from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.core.validators import RegexValidator
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.properties.models import Property
from .models import CaretakerProfile, User, UserProfile, OwnerProfile, TenantProfile, PaystackSubaccount

User = get_user_model()

# ==================== REGISTRATION WIZARD FORMS ====================

class RegistrationStep1Form(forms.ModelForm):
    """Step 1: Basic Information"""
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Enter password'
        }),
        label='Password'
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Confirm password'
        }),
        label='Confirm Password'
    )

    accept_terms = forms.BooleanField(
        required=True,
        label='I accept the Terms of Service and Privacy Policy',
        error_messages={'required': 'You must accept the Terms of Service and Privacy Policy to create an account.'},
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
        })
    )
    
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter your email'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter your first name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter your last name'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter your phone number'
            }),
        }
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email
    
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            # Ensure phone is stored as a string
            return str(phone)
        return phone


class RegistrationStep2Form(forms.ModelForm):
    """Step 2: Business Details (for owners)"""
    
    class Meta:
        model = OwnerProfile
        fields = ['company_name', 'company_registration_number', 'tax_pin', 'business_license']
        widgets = {
            'company_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter your company/business name'
            }),
            'company_registration_number': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter business registration number'
            }),
            'tax_pin': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter your tax PIN'
            }),
            'business_license': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
            }),
        }
    
    def clean_business_license(self):
        """Validate business license file"""
        file = self.cleaned_data.get('business_license')
        if file:
            # Check file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                raise forms.ValidationError('File size must be less than 10MB.')
            
            # Check file extension
            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
            import os
            ext = os.path.splitext(file.name)[1].lower()
            if ext not in allowed_extensions:
                raise forms.ValidationError('File must be PDF, JPG, JPEG, PNG, DOC, or DOCX.')
        
        return file

class RegistrationStep3Form(forms.Form):
    """Step 3: Bank Account Details (for owners)"""
    
    bank_code = forms.ChoiceField(
        choices=[('', 'Select Bank')],
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500'
        }),
        label='Bank Name'
    )
    
    account_number = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Enter account number'
        }),
        label='Account Number'
    )
    
    account_name = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Enter account holder name'
        }),
        label='Account Holder Name'
    )
    
    def __init__(self, *args, bank_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        if bank_choices:
            self.fields['bank_code'].choices = [('', 'Select Bank')] + bank_choices
    
    def clean_account_number(self):
        account_number = self.cleaned_data.get('account_number')
        if not account_number:
            raise forms.ValidationError('Account number is required.')
        account_number = ''.join(filter(str.isdigit, account_number))
        if len(account_number) < 10:
            raise forms.ValidationError('Account number must be at least 10 digits.')
        return account_number


# ==================== EXISTING FORMS (KEEP AS IS) ====================

class UserRegistrationForm(UserCreationForm):
    # Keep this exactly as you have it - used for admin/manual creation
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
        user.username = self.cleaned_data['email']
        if commit:
            user.save()
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
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'appearance-none rounded-md relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm',
            'placeholder': 'Email address'
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError('No user found with this email address.')
        return email



# ==================== PAYSTACK BANK ACCOUNT FORM (UPDATED) ====================

class PaystackSubaccountForm(forms.ModelForm):
    """Form for setting up Paystack subaccount for bank account information"""
    
    bank_code = forms.ChoiceField(
        choices=[('', 'Select Bank')],
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
    
    def __init__(self, *args, bank_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        if bank_choices is not None:
            self.fields['bank_code'].choices = [('', 'Select Bank')] + bank_choices
    
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


# ==================== CARETAKER FORMS ====================

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