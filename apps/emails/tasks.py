from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def send_email_task(self, subject, to_email, template_name, context=None, from_email=None):
    """
    Async task to send email
    """
    if context is None:
        context = {}
    
    from_email = from_email or settings.DEFAULT_FROM_EMAIL
    
    try:
        # Render HTML content
        html_content = render_to_string(template_name, context)
        text_content = strip_tags(html_content)
        
        # Create email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[to_email]
        )
        email.attach_alternative(html_content, "text/html")
        
        # Send email
        email.send()
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        # Retry the task
        raise self.retry(exc=e, countdown=60)  # Retry after 60 seconds