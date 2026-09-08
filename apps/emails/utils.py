import json

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import logging
from .tasks import send_email_task


logger = logging.getLogger(__name__)

class EmailService:
    """Service class for sending emails asynchronously"""
    
    @staticmethod
    def send_email(subject, to_email, template_name, context=None, from_email=None, async_mode=None):
        """
        Send an email using HTML template
        """
        if context is None:
            context = {}
        
        from_email = from_email or settings.DEFAULT_FROM_EMAIL
        if async_mode is None:
            async_mode = getattr(settings, 'EMAIL_ASYNC', False)
        
        if async_mode:
            # Send asynchronously using Celery
            try:
                json.dumps(context)
                send_email_task.delay(subject, to_email, template_name, context, from_email)
                logger.info(f"Email task queued for {to_email}")
                return True
            except TypeError:
                logger.warning('Email context is not JSON serializable; sending synchronously')
                return EmailService.send_email_sync(subject, to_email, template_name, context, from_email)
            except Exception as e:
                logger.error(f"Failed to queue email task for {to_email}: {str(e)}")
                # Fall back to sync sending
                return EmailService.send_email_sync(subject, to_email, template_name, context, from_email)
        else:
            # Send synchronously
            return EmailService.send_email_sync(subject, to_email, template_name, context, from_email)
    
    @staticmethod
    def send_email_sync(subject, to_email, template_name, context=None, from_email=None):
        """
        Send email synchronously (fallback)
        """
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        
        if context is None:
            context = {}
        
        from_email = from_email or settings.DEFAULT_FROM_EMAIL
        
        try:
            html_content = render_to_string(template_name, context)
            text_content = strip_tags(html_content)
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=[to_email]
            )
            email.attach_alternative(html_content, "text/html")
            email.send()
            logger.info(f"Email sent successfully to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    @staticmethod
    def send_activation_email(user, activation_link):
        """Send account activation email"""
        subject = "Activate Your Winda Account"
        template_name = 'emails/activation_email.html'
        context = {
            'user': user,
            'full_name': user.get_full_name(),
            'activation_link': activation_link,
            'support_email': 'support@winda.co.ke',
            'site_name': 'Winda',
        }
        # Use async mode to prevent timeout
        return EmailService.send_email(subject, user.email, template_name, context, async_mode=False)
            
    @staticmethod
    def send_welcome_email(user):
        """Send welcome email to new user"""
        subject = f"Welcome to Winda, {user.get_full_name()}!"
        template_name = 'emails/welcome.html'
        context = {
            'user': user,
            'full_name': user.get_full_name(),
            'login_url': f'{settings.SITE_URL}/accounts/login/',
        }
        return EmailService.send_email(subject, user.email, template_name, context)
    
    @staticmethod
    def send_password_reset_email(user, reset_link):
        """Send password reset email"""
        subject = "Reset Your Winda Password"
        template_name = 'emails/password_reset.html'
        context = {
            'user': user,
            'full_name': user.get_full_name(),
            'reset_link': reset_link,
            'support_email': 'support@winda.co.ke',
        }
        return EmailService.send_email(subject, user.email, template_name, context)
    
    @staticmethod
    def send_application_status_email(application):
        """Send application status update email"""
        subject = f"Application Status Update - {application.property.title}"
        template_name = 'emails/application_status.html'
        context = {
            'user': application.tenant,
            'full_name': application.tenant.get_full_name(),
            'application': application,
            'property': application.property,
            'status': application.get_status_display(),
            'status_class': application.status.lower(),
            'property_url': f'{settings.SITE_URL}/properties/{application.property.id}/',
        }
        return EmailService.send_email(subject, application.tenant.email, template_name, context)

    @staticmethod
    def send_application_received_email(application):
        """Notify the property owner that a tenant submitted an application."""
        owner = application.property.owner.user
        context = {
            'full_name': owner.get_full_name(),
            'application': application,
            'property': application.property,
            'tenant': application.tenant,
            'application_url': f'{settings.SITE_URL}/tenants/owner/tenants/pending/{application.id}/',
            'support_email': 'support@winda.co.ke',
        }
        return EmailService.send_email(
            f'New Application - {application.property.title}',
            owner.email,
            'emails/application_received.html',
            context,
        )
    
    @staticmethod
    def send_payment_confirmation_email(payment):
        """Send payment confirmation email"""
        subject = f"Payment Confirmation - {payment.payment_reference}"
        template_name = 'emails/payment_confirmation.html'
        context = {
            'user': payment.payer,
            'full_name': payment.payer.get_full_name(),
            'payment': payment,
            'amount': payment.amount,
            'payment_type': payment.get_payment_type_display(),
            'payment_link': f'{settings.SITE_URL}/payments/{payment.id}/',
            'support_email': 'support@winda.co.ke',
        }
        sent = EmailService.send_email(subject, payment.payer.email, template_name, context)
        if payment.recipient and payment.recipient.email:
            owner_context = dict(context)
            owner_context['user'] = payment.recipient
            owner_context['full_name'] = payment.recipient.get_full_name()
            sent = EmailService.send_email(subject, payment.recipient.email, template_name, owner_context) and sent
        return sent
    
    @staticmethod
    def send_lease_created_email(lease):
        """Send lease created email"""
        subject = f"Lease Agreement Created - {lease.property.title}"
        template_name = 'emails/lease_created.html'
        context = {
            'user': lease.tenant,
            'full_name': lease.tenant.get_full_name(),
            'lease': lease,
            'property': lease.property,
            'unit': lease.unit,
            'start_date': lease.start_date,
            'end_date': lease.end_date,
            'monthly_rent': lease.monthly_rent,
            'lease_url': f'{settings.SITE_URL}/tenants/leases/{lease.id}/',
            'support_email': 'support@winda.co.ke',
        }
        sent = EmailService.send_email(subject, lease.tenant.email, template_name, context)
        owner = lease.property.owner.user
        owner_context = dict(context)
        owner_context['user'] = owner
        owner_context['full_name'] = owner.get_full_name()
        sent = EmailService.send_email(subject, owner.email, template_name, owner_context) and sent
        return sent
    
    @staticmethod
    def send_lease_signed_email(lease):
        """Send lease signed confirmation email"""
        subject = f"Lease Signed - Welcome to Your New Home!"
        template_name = 'emails/lease_signed.html'
        context = {
            'user': lease.tenant,
            'full_name': lease.tenant.get_full_name(),
            'lease': lease,
            'property': lease.property,
            'unit': lease.unit,
            'start_date': lease.start_date,
            'end_date': lease.end_date,
            'monthly_rent': lease.monthly_rent,
            'support_email': 'support@winda.co.ke',
        }
        sent = EmailService.send_email(subject, lease.tenant.email, template_name, context)
        owner = lease.property.owner.user
        owner_context = dict(context)
        owner_context['user'] = owner
        owner_context['full_name'] = owner.get_full_name()
        sent = EmailService.send_email(subject, owner.email, template_name, owner_context) and sent
        return sent
    
    @staticmethod
    def send_maintenance_request_email(request_obj):
        """Send maintenance request notification email"""
        subject = f"Maintenance Request - {request_obj.title}"
        template_name = 'emails/maintenance_request.html'
        context = {
            'user': request_obj.tenant,
            'full_name': request_obj.tenant.get_full_name(),
            'request': request_obj,
            'property': request_obj.property,
            'request_url': f'{settings.SITE_URL}/maintenance/{request_obj.id}/',
            'support_email': 'support@winda.co.ke',
        }
        return EmailService.send_email(subject, request_obj.tenant.email, template_name, context)
    
    @staticmethod
    def send_tenant_notice_email(tenant, notice_type, message, owner_name):
        """Send tenant notice email"""
        subject = f"Notice from {owner_name} - {notice_type}"
        template_name = 'emails/tenant_notice.html'
        context = {
            'user': tenant,
            'full_name': tenant.get_full_name(),
            'notice_type': notice_type,
            'message': message,
            'owner_name': owner_name,
            'support_email': 'support@winda.co.ke',
        }
        return EmailService.send_email(subject, tenant.email, template_name, context)