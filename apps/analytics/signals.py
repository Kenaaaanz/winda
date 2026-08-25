from django.db.models.aggregates import Sum
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import models
from decimal import Decimal

from apps.properties.models import Property, PropertyImage, Unit
from apps.tenants.models import TenantApplication, Lease
from apps.payments.models import Payment
from apps.maintenance.models import MaintenanceRequest
from apps.accounts.models import OwnerProfile

# Import the models from the analytics app
from .models import AnalyticsEvent, DailyAnalyticsReport

User = get_user_model()


# ========================================
# ANALYTICS EVENT LOGGING SIGNALS
# ========================================

@receiver(post_save, sender=User)
def log_user_creation(sender, instance, created, **kwargs):
    """Log when a user is created"""
    if created:
        AnalyticsEvent.objects.create(
            user=instance,
            event_type='USER_REGISTER',
            data={
                'user_type': instance.user_type,
                'email': instance.email,
                'first_name': instance.first_name,
                'last_name': instance.last_name,
                'is_active': instance.is_active,
            }
        )


@receiver(post_save, sender=Property)
def log_property_creation(sender, instance, created, **kwargs):
    """Log when a property is created"""
    if created:
        AnalyticsEvent.objects.create(
            user=instance.owner.user,
            event_type='PROPERTY_LIST',
            property=instance,
            data={
                'property_type': instance.property_type,
                'city': instance.city,
                'is_multi_unit': instance.is_multi_unit,
                'rental_price': float(instance.rental_price) if instance.rental_price else None,
                'bedrooms': instance.bedrooms,
                'bathrooms': instance.bathrooms,
                'verification_status': instance.verification_status,
            }
        )
    else:
        # Log property updates (e.g., verification status change)
        if 'verification_status' in kwargs.get('update_fields', []):
            AnalyticsEvent.objects.create(
                user=instance.owner.user,
                event_type='PROPERTY_LIST',
                property=instance,
                data={
                    'action': 'update',
                    'verification_status': instance.verification_status,
                    'title': instance.title,
                }
            )


@receiver(post_delete, sender=Property)
def log_property_deletion(sender, instance, **kwargs):
    """Log when a property is deleted"""
    AnalyticsEvent.objects.create(
        user=instance.owner.user,
        event_type='PROPERTY_LIST',
        property=instance,
        data={
            'action': 'delete',
            'title': instance.title,
            'deleted_at': timezone.now().isoformat()
        }
    )


@receiver(post_save, sender=Unit)
def log_unit_creation(sender, instance, created, **kwargs):
    """Log when a unit is created"""
    if created:
        AnalyticsEvent.objects.create(
            user=instance.property_obj.owner.user,
            event_type='UNIT_CREATE',
            property=instance.property_obj,
            unit=instance,
            data={
                'unit_number': instance.unit_number,
                'bedrooms': instance.bedrooms,
                'bathrooms': instance.bathrooms,
                'rental_price': float(instance.get_rental_price()) if instance.get_rental_price() else None,
                'status': instance.status,
                'is_available': instance.is_available,
            }
        )


@receiver(post_save, sender=TenantApplication)
def log_application_event(sender, instance, created, **kwargs):
    """Log when a tenant application is created or updated"""
    if created:
        AnalyticsEvent.objects.create(
            user=instance.tenant,
            event_type='APPLICATION_SUBMIT',
            property=instance.property,
            unit=instance.unit,
            data={
                'property_id': str(instance.property.id),
                'unit_id': str(instance.unit.id) if instance.unit else None,
                'status': instance.status,
                'intended_move_in_date': instance.intended_move_in_date.isoformat() if instance.intended_move_in_date else None,
                'preferred_lease_duration': instance.preferred_lease_duration,
                'monthly_income': float(instance.monthly_income) if instance.monthly_income else None,
                'employment_status': instance.employment_status,
            }
        )
    else:
        # Log status changes
        if 'status' in kwargs.get('update_fields', []):
            event_type = 'APPLICATION_APPROVE' if instance.status == 'APPROVED' else 'APPLICATION_REJECT'
            AnalyticsEvent.objects.create(
                user=instance.tenant,
                event_type=event_type,
                property=instance.property,
                unit=instance.unit,
                data={
                    'status': instance.status,
                    'owner_notes': instance.owner_notes,
                    'reviewed_at': instance.reviewed_at.isoformat() if instance.reviewed_at else None,
                    'reviewed_by': str(instance.reviewed_by.id) if instance.reviewed_by else None,
                }
            )


@receiver(post_save, sender=Lease)
def log_lease_event(sender, instance, created, **kwargs):
    """Log when a lease is created or updated"""
    if created:
        AnalyticsEvent.objects.create(
            user=instance.tenant,
            event_type='LEASE_SIGN',
            property=instance.property,
            unit=instance.unit,
            data={
                'property_id': str(instance.property.id),
                'unit_id': str(instance.unit.id) if instance.unit else None,
                'monthly_rent': float(instance.monthly_rent),
                'security_deposit': float(instance.security_deposit),
                'start_date': instance.start_date.isoformat() if instance.start_date else None,
                'end_date': instance.end_date.isoformat() if instance.end_date else None,
                'status': instance.status,
                'termination_notice_period': instance.termination_notice_period,
            }
        )
    else:
        # Log status changes
        if instance.status == 'TERMINATED':
            AnalyticsEvent.objects.create(
                user=instance.tenant,
                event_type='LEASE_TERMINATE',
                property=instance.property,
                unit=instance.unit,
                data={
                    'terminated_at': instance.terminated_at.isoformat() if instance.terminated_at else None,
                    'status': instance.status,
                    'reason': kwargs.get('reason', ''),
                }
            )
        elif instance.status == 'ACTIVE':
            AnalyticsEvent.objects.create(
                user=instance.tenant,
                event_type='LEASE_SIGN',
                property=instance.property,
                unit=instance.unit,
                data={
                    'action': 'activate',
                    'signed_at': instance.signed_at.isoformat() if instance.signed_at else None,
                    'status': instance.status,
                }
            )


@receiver(post_save, sender=Payment)
def log_payment_event(sender, instance, created, **kwargs):
    """Log when a payment is created or updated"""
    if created:
        AnalyticsEvent.objects.create(
            user=instance.payer,
            event_type='PAYMENT_INITIATE',
            property=instance.property,
            unit=instance.unit if hasattr(instance, 'unit') else None,
            data={
                'amount': float(instance.amount),
                'payment_type': instance.payment_type,
                'property_id': str(instance.property.id) if instance.property else None,
                'unit_id': str(instance.unit.id) if hasattr(instance, 'unit') and instance.unit else None,
                'payment_method': instance.payment_method,
                'payment_reference': instance.payment_reference,
                'status': instance.status,
                'due_date': instance.due_date.isoformat() if instance.due_date else None,
            }
        )
    else:
        # Log status changes (e.g., from PENDING to COMPLETED)
        if instance.status == 'COMPLETED':
            AnalyticsEvent.objects.create(
                user=instance.payer,
                event_type='PAYMENT_COMPLETE',
                property=instance.property,
                unit=instance.unit if hasattr(instance, 'unit') else None,
                data={
                    'amount': float(instance.amount),
                    'payment_type': instance.payment_type,
                    'payment_reference': instance.payment_reference,
                    'paid_at': instance.paid_at.isoformat() if instance.paid_at else None,
                    'payment_method': instance.payment_method,
                }
            )
            # Also log platform fee
            if instance.property and instance.property.owner:
                platform_fee = instance.amount * Decimal('0.03')
                AnalyticsEvent.objects.create(
                    user=instance.property.owner.user,
                    event_type='PAYMENT_COMPLETE',
                    property=instance.property,
                    data={
                        'amount': float(platform_fee),
                        'payment_type': 'PLATFORM_FEE',
                        'payment_reference': instance.payment_reference,
                        'paid_at': instance.paid_at.isoformat() if instance.paid_at else None,
                        'original_payment_id': str(instance.id),
                        'original_amount': float(instance.amount),
                    }
                )
        elif instance.status == 'FAILED':
            AnalyticsEvent.objects.create(
                user=instance.payer,
                event_type='PAYMENT_FAIL',
                property=instance.property,
                unit=instance.unit if hasattr(instance, 'unit') else None,
                data={
                    'amount': float(instance.amount),
                    'payment_type': instance.payment_type,
                    'failure_reason': instance.failure_reason,
                    'payment_reference': instance.payment_reference,
                }
            )


@receiver(post_save, sender=MaintenanceRequest)
def log_maintenance_event(sender, instance, created, **kwargs):
    """Log when a maintenance request is created or updated"""
    if created:
        AnalyticsEvent.objects.create(
            user=instance.tenant,
            event_type='MAINTENANCE_REQUEST',
            property=instance.property,
            unit=instance.unit if hasattr(instance, 'unit') else None,
            data={
                'property_id': str(instance.property.id),
                'unit_id': str(instance.unit.id) if hasattr(instance, 'unit') and instance.unit else None,
                'category': instance.category,
                'priority': instance.priority,
                'title': instance.title,
                'status': instance.status,
                'description': instance.description[:200],  # Truncate for storage
            }
        )
    else:
        # Log status updates
        if instance.status == 'RESOLVED':
            AnalyticsEvent.objects.create(
                user=instance.tenant,
                event_type='MAINTENANCE_RESOLVE',
                property=instance.property,
                unit=instance.unit if hasattr(instance, 'unit') else None,
                data={
                    'status': instance.status,
                    'resolved_at': instance.resolved_at.isoformat() if instance.resolved_at else None,
                    'resolution_notes': instance.resolution_notes[:200] if instance.resolution_notes else None,
                    'assigned_to': str(instance.assigned_to.id) if instance.assigned_to else None,
                }
            )
        elif instance.status in ['ASSIGNED', 'IN_PROGRESS']:
            AnalyticsEvent.objects.create(
                user=instance.tenant,
                event_type='MAINTENANCE_REQUEST',
                property=instance.property,
                unit=instance.unit if hasattr(instance, 'unit') else None,
                data={
                    'action': 'status_update',
                    'status': instance.status,
                    'assigned_to': str(instance.assigned_to.id) if instance.assigned_to else None,
                    'updated_at': timezone.now().isoformat(),
                }
            )


@receiver(post_save, sender=PropertyImage)
def log_image_upload_event(sender, instance, created, **kwargs):
    """Log when property images are uploaded"""
    if created:
        AnalyticsEvent.objects.create(
            user=instance.property.owner.user,
            event_type='PROPERTY_VIEW',  # Using PROPERTY_VIEW as a proxy for image upload
            property=instance.property,
            data={
                'action': 'image_upload',
                'is_main': instance.is_main,
                'image_count': instance.property.property_images.filter(is_active=True).count(),
                'image_id': str(instance.id),
            }
        )


# ========================================
# OWNER PROFILE STATS UPDATES
# ========================================

@receiver(post_save, sender=TenantApplication)
def update_owner_stats_on_application(sender, instance, **kwargs):
    """Update owner's tenant count when application is approved"""
    if instance.status == 'APPROVED':
        try:
            owner = instance.property.owner
            # Count unique tenants with approved applications
            tenant_count = TenantApplication.objects.filter(
                property__owner=owner,
                status='APPROVED'
            ).values('tenant').distinct().count()
            owner.total_tenants = tenant_count
            owner.save(update_fields=['total_tenants'])
        except (OwnerProfile.DoesNotExist, AttributeError):
            pass


@receiver(post_save, sender=Payment)
def update_owner_stats_on_payment(sender, instance, **kwargs):
    """Update owner's total revenue when payment is completed"""
    if instance.status == 'COMPLETED' and instance.property:
        try:
            owner = instance.property.owner
            total_revenue = Payment.objects.filter(
                property__owner=owner,
                status='COMPLETED'
            ).aggregate(total=models.Sum('amount'))['total'] or 0
            owner.total_revenue = total_revenue
            owner.save(update_fields=['total_revenue'])
        except (OwnerProfile.DoesNotExist, AttributeError):
            pass


@receiver(post_save, sender=Property)
def update_owner_property_count(sender, instance, created, **kwargs):
    """Update owner's property count"""
    if created:
        try:
            owner = instance.owner
            property_count = Property.objects.filter(owner=owner).count()
            owner.total_properties = property_count
            owner.save(update_fields=['total_properties'])
        except (OwnerProfile.DoesNotExist, AttributeError):
            pass


@receiver(post_delete, sender=Property)
def update_owner_property_count_on_delete(sender, instance, **kwargs):
    """Update owner's property count when property is deleted"""
    try:
        owner = instance.owner
        property_count = Property.objects.filter(owner=owner).count()
        owner.total_properties = property_count
        owner.save(update_fields=['total_properties'])
    except (OwnerProfile.DoesNotExist, AttributeError):
        pass


@receiver(post_save, sender=Unit)
def update_property_unit_counts(sender, instance, created, **kwargs):
    """Update property's unit counts when units are added or changed"""
    try:
        property_obj = instance.property_obj
        if property_obj:
            total_units = property_obj.units.count()
            available_units = property_obj.units.filter(is_available=True).count()
            property_obj.total_units = total_units
            property_obj.available_units = available_units
            property_obj.save(update_fields=['total_units', 'available_units'])
    except (AttributeError, property_obj.DoesNotExist):
        pass


@receiver(post_delete, sender=Unit)
def update_property_unit_counts_on_delete(sender, instance, **kwargs):
    """Update property's unit counts when unit is deleted"""
    try:
        property_obj = instance.property_obj
        if property_obj:
            total_units = property_obj.units.count()
            available_units = property_obj.units.filter(is_available=True).count()
            property_obj.total_units = total_units
            property_obj.available_units = available_units
            property_obj.save(update_fields=['total_units', 'available_units'])
    except (AttributeError, property_obj.DoesNotExist):
        pass


@receiver(post_save, sender=Lease)
def update_unit_status_on_lease(sender, instance, created, **kwargs):
    """Update unit status when lease is created"""
    if created and instance.unit:
        try:
            instance.unit.status = 'BOOKED'
            instance.unit.is_available = False
            instance.unit.current_tenant = instance.tenant
            instance.unit.save(update_fields=['status', 'is_available', 'current_tenant'])
            
            # Update property availability
            property_obj = instance.property
            if property_obj:
                available_units = property_obj.units.filter(is_available=True).count()
                property_obj.available_units = available_units
                if available_units == 0:
                    property_obj.availability_status = 'RENTED'
                property_obj.save(update_fields=['available_units', 'availability_status'])
        except (AttributeError, property_obj.DoesNotExist):
            pass


@receiver(post_save, sender=Lease)
def update_unit_status_on_lease_termination(sender, instance, **kwargs):
    """Update unit status when lease is terminated"""
    if instance.status == 'TERMINATED' and instance.unit:
        try:
            instance.unit.status = 'AVAILABLE'
            instance.unit.is_available = True
            instance.unit.current_tenant = None
            instance.unit.save(update_fields=['status', 'is_available', 'current_tenant'])
            
            # Update property availability
            property_obj = instance.property
            if property_obj:
                available_units = property_obj.units.filter(is_available=True).count()
                property_obj.available_units = available_units
                property_obj.availability_status = 'AVAILABLE' if available_units > 0 else 'RENTED'
                property_obj.save(update_fields=['available_units', 'availability_status'])
        except (AttributeError, property_obj.DoesNotExist):
            pass


# ========================================
# ANALYTICS METRIC AGGREGATION
# ========================================

def aggregate_daily_metrics():
    """Function to aggregate daily analytics metrics"""
    from .models import AnalyticsEvent
    
    today = timezone.now().date()
    
    # Aggregate property views
    property_views = AnalyticsEvent.objects.filter(
        event_type='PROPERTY_VIEW',
        created_at__date=today
    ).count()
    
    # Aggregate applications
    applications = AnalyticsEvent.objects.filter(
        event_type='APPLICATION_SUBMIT',
        created_at__date=today
    ).count()
    
    # Aggregate payments
    payments = AnalyticsEvent.objects.filter(
        event_type='PAYMENT_COMPLETE',
        created_at__date=today
    ).count()
    
    payment_total = Payment.objects.filter(
        status='COMPLETED',
        paid_at__date=today
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Aggregate maintenance
    maintenance = AnalyticsEvent.objects.filter(
        event_type='MAINTENANCE_REQUEST',
        created_at__date=today
    ).count()
    
    # Aggregate new users
    new_users = User.objects.filter(
        date_joined__date=today
    ).count()
    
    # Create or update daily report
    from .models import DailyAnalyticsReport
    report, created = DailyAnalyticsReport.objects.get_or_create(
        date=today,
        defaults={
            'total_users': User.objects.filter(is_active=True).count(),
            'active_users': AnalyticsEvent.objects.filter(
                created_at__date=today
            ).values('user').distinct().count(),
            'new_users': new_users,
            'total_properties': Property.objects.count(),
            'new_properties': Property.objects.filter(created_at__date=today).count(),
            'properties_views': property_views,
            'total_payments': payments,
            'total_amount': payment_total,
            'new_applications': applications,
            'maintenance_requests': maintenance,
        }
    )
    
    if not created:
        report.total_users = User.objects.filter(is_active=True).count()
        report.active_users = AnalyticsEvent.objects.filter(
            created_at__date=today
        ).values('user').distinct().count()
        report.new_users = new_users
        report.total_properties = Property.objects.count()
        report.new_properties = Property.objects.filter(created_at__date=today).count()
        report.properties_views = property_views
        report.total_payments = payments
        report.total_amount = payment_total
        report.new_applications = applications
        report.maintenance_requests = maintenance
        report.save()
    
    return report


def aggregate_weekly_metrics():
    """Aggregate weekly analytics metrics"""
    today = timezone.now().date()
    week_start = today - timezone.timedelta(days=7)
    
    # Aggregate for the week
    week_data = {
        'total_events': AnalyticsEvent.objects.filter(
            created_at__date__gte=week_start,
            created_at__date__lte=today
        ).count(),
        'new_users': User.objects.filter(date_joined__date__gte=week_start).count(),
        'new_properties': Property.objects.filter(created_at__date__gte=week_start).count(),
        'new_applications': TenantApplication.objects.filter(
            created_at__date__gte=week_start
        ).count(),
        'total_payments': Payment.objects.filter(
            status='COMPLETED',
            paid_at__date__gte=week_start
        ).count(),
        'payment_total': Payment.objects.filter(
            status='COMPLETED',
            paid_at__date__gte=week_start
        ).aggregate(total=Sum('amount'))['total'] or 0,
    }
    
    return week_data


def aggregate_monthly_metrics():
    """Aggregate monthly analytics metrics"""
    today = timezone.now().date()
    month_start = today.replace(day=1)
    
    # Aggregate for the month
    month_data = {
        'total_events': AnalyticsEvent.objects.filter(
            created_at__date__gte=month_start,
            created_at__date__lte=today
        ).count(),
        'new_users': User.objects.filter(date_joined__date__gte=month_start).count(),
        'new_properties': Property.objects.filter(created_at__date__gte=month_start).count(),
        'new_applications': TenantApplication.objects.filter(
            created_at__date__gte=month_start
        ).count(),
        'total_payments': Payment.objects.filter(
            status='COMPLETED',
            paid_at__date__gte=month_start
        ).count(),
        'payment_total': Payment.objects.filter(
            status='COMPLETED',
            paid_at__date__gte=month_start
        ).aggregate(total=Sum('amount'))['total'] or 0,
    }
    
    return month_data