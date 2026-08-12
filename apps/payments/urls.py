from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment List and Details
    path('', views.payment_list, name='list'),
    path('<uuid:payment_id>/', views.payment_detail, name='detail'),
    
    # Payment Initiation
    path('initiate/', views.initiate_payment, name='initiate'),
    path('callback/', views.payment_callback, name='callback'),
    path('retry/<uuid:payment_id>/', views.retry_payment, name='retry'),
    
    # Manual Approval (Owner only)
    path('<uuid:payment_id>/approve/', views.approve_payment_manual, name='approve_manual'),
    path('<uuid:payment_id>/reject/', views.reject_payment_manual, name='reject_manual'),
    
    # Paystack Sync
    path('<uuid:payment_id>/sync/', views.sync_payment_paystack, name='sync_paystack'),
    path('sync-all/', views.sync_all_payments, name='sync_all'),
    
    # Manual Verification (for testing)
    path('verify/<uuid:payment_id>/', views.verify_payment_manual, name='verify_manual'),
    
    # Subscriptions
    path('subscription/plans/', views.subscription_plans, name='subscription_plans'),
    path('subscription/cancel/', views.cancel_subscription, name='cancel_subscription'),
    
    # Invoices
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/<uuid:invoice_id>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<uuid:invoice_id>/download/', views.download_invoice, name='download_invoice'),
    
    # Statistics (Owner only)
    path('stats/', views.payment_stats, name='stats'),
]