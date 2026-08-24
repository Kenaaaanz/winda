from django.urls import path
from django.views.generic import TemplateView

app_name = 'legal'

urlpatterns = [
    path('terms/', TemplateView.as_view(template_name='legal/terms_of_service.html'), name='terms_of_service'),
    path('privacy/', TemplateView.as_view(template_name='legal/privacy_policy.html'), name='privacy_policy'),
]