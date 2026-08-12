import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'winda.settings')

app = Celery('winda')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'send-payment-reminders': {
        'task': 'apps.payments.tasks.send_payment_reminders',
        'schedule': crontab(hour=8, minute=0),  # Run daily at 8 AM
    },
    'update-subscription-status': {
        'task': 'apps.accounts.tasks.update_subscription_status',
        'schedule': crontab(hour=0, minute=0),  # Run daily at midnight
    },
    'cleanup-expired-tokens': {
        'task': 'apps.accounts.tasks.cleanup_expired_tokens',
        'schedule': crontab(hour=2, minute=0),  # Run daily at 2 AM
    },
    'generate-analytics-report': {
        'task': 'apps.analytics.tasks.generate_daily_report',
        'schedule': crontab(hour=23, minute=59),  # Run daily at 11:59 PM
    },
}