from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('register/', views.register, name='register'),
    path('login/', views.CustomLoginView.as_view(), name='login'), 
    path('logout/', views.custom_logout, name='logout'),
    path('activate/<uidb64>/<token>/', views.activate_account, name='activate'),
    
    # Password Reset - Using Django's built-in views with correct URL names
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='accounts/password_reset.html',
             email_template_name='accounts/password_reset_email.html',
             subject_template_name='accounts/password_reset_subject.txt',
             success_url='done/'  # This tells it to redirect to password_reset/done/
         ), 
         name='password_reset'),
    
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='accounts/password_reset_done.html'
         ), 
         name='password_reset_done'),  # This is the name Django expects
    
    path('password-reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='accounts/password_reset_confirm.html',
             success_url='/accounts/password-reset/complete/'
         ), 
         name='password_reset_confirm'),
    
    path('password-reset/complete/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='accounts/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
    
    # Dashboard - This is the main dashboard URL
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Profile
    path('profile/', views.profile, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('profile/update-business/', views.update_business, name='update_business'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('profile/delete/', views.delete_account, name='delete_account'),
    path('profile/update-picture/', views.update_profile_picture, name='update_profile_picture'),

    
    # User Management (Admin only)
    path('users/', views.user_list, name='user_list'),
    path('users/<uuid:user_id>/', views.user_detail, name='user_detail'),
    path('users/<uuid:user_id>/block/', views.block_user, name='block_user'),
    path('users/<uuid:user_id>/unblock/', views.unblock_user, name='unblock_user'),
    
    # Caretaker Management (Owner only)
    path('caretakers/', views.manage_caretakers, name='manage_caretakers'),
    
    # Bank Account Setup (Owner only)
    path('bank-account/setup/', views.setup_bank_account, name='setup_bank_account'),
    path('bank-account/', views.bank_account_details, name='bank_account_details'),
    path('bank-account/update/', views.update_bank_account, name='update_bank_account'),
    path('bank-account/delete/', views.delete_bank_account, name='delete_bank_account'),

    #resend activation email
    path('resend-activation/', views.resend_activation_email, name='resend_activation'),

    # Caretaker Management - HTML Views
    path('caretakers/', views.caretaker_list, name='caretaker_list'),
    path('caretakers/invite/', views.caretaker_invite, name='caretaker_invite'),
    path('caretaker/dashboard/', views.caretaker_dashboard, name='caretaker_dashboard'),

    # Use string pattern for edit and delete - this handles both UUID and integer IDs
    path('caretakers/<str:caretaker_id>/edit/', views.caretaker_edit, name='caretaker_edit'),
    path('caretakers/<str:caretaker_id>/delete/', views.caretaker_delete, name='caretaker_delete'),
    
    
    # Caretaker API Endpoints (NEW)
    path('api/caretakers/', views.caretaker_api_list, name='api_caretaker_list'),
    path('api/caretakers/delete/', views.caretaker_api_delete, name='api_caretaker_delete'),
    path('api/caretakers/update/', views.caretaker_api_update, name='api_caretaker_update'),

]