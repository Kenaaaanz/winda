from allauth.account.adapter import DefaultAccountAdapter
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()

class CustomAccountAdapter(DefaultAccountAdapter):
    """Custom adapter for allauth to work with custom user model"""
    
    def get_login_redirect_url(self, request):
        """Override login redirect"""
        return reverse('dashboard')
    
    def get_signup_redirect_url(self, request):
        """Override signup redirect"""
        return reverse('dashboard')
    
    def save_user(self, request, user, form, commit=True):
        """Save user with custom fields"""
        user = super().save_user(request, user, form, commit=False)
        
        # Set custom fields if they exist in the form
        if 'phone' in form.cleaned_data:
            user.phone = form.cleaned_data['phone']
        if 'user_type' in form.cleaned_data:
            user.user_type = form.cleaned_data['user_type']
        
        if commit:
            user.save()
        return user