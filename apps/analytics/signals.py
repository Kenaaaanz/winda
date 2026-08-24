from django.db.models.aggregates import Sum
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.properties.models import Property, PropertyImage, Unit
from apps.tenants.models import TenantApplication, Lease
from apps.payments.models import Payment
from apps.maintenance.models import MaintenanceRequest
from .models import UserActivity, AnalyticsMetric
from decimal import Decimal

User = get_user_model()


# ========================================
# USER ACTIVITY LOGGING SIGNALS
# ========================================

@receiver(post_save, sender=User)
def log_user_creation(sender, instance, created, **kwargs):
    """Log when a user is created"""
    if created:
        UserActivity.objects.create(
            user=instance,
            activity_type='CREATE',
            description=f'User {instance.get_full_name()} registered',
            related_object_type='user',
            related_object_id=str(instance.id),
            data={
                'user_type': instance.user_type,
                'email': instance.email
            }
        )


@receiver(post_save, sender=Property)
def log_property_creation(sender, instance, created, **kwargs):
    """Log when a property is created"""
    if created:
        # User activity
        UserActivity.objects.create(
            user=instance.owner.user,
            activity_type='CREATE',
            description=f'Created property: {instance.title}',
            related_object_type='property',
            related_object_id=str(instance.id),
            data={
                'property_type': instance.property_type,
                'city': instance.city,
                'is_multi_unit': instance.is_multi_unit
            }
        )
        
        # Analytics metric
        AnalyticsMetric.objects.create(
            metric_type='PROPERTY_VIEWS',
            owner=instance.owner,
            property=instance,
            count=0,
            date=timezone.now().date(),
            metadata={
                'title': instance.title,
                'property_type': instance.property_type
            }
        )


@receiver(post_delete, sender=Property)
def log_property_deletion(sender, instance, **kwargs):
    """Log when a property is deleted"""
    UserActivity.objects.create(
        user=instance.owner.user,
        activity_type='DELETE',
        description=f'Deleted property: {instance.title}',
        related_object_type='property',
        related_object_id=str(instance.id)
    )


@receiver(post_save, sender=Unit)
def log_unit_creation(sender, instance, created, **kwargs):
    """Log when a unit is created"""
    if created:
        UserActivity.objects.create(
            user=instance.property_obj.owner.user,
            activity_type='CREATE',
            description=f'Created unit {instance.unit_number} for {instance.property_obj.title}',
            related_object_type='unit',
            related_object_id=str(instance.id),
            data={
                'property_id': str(instance.property_obj.id),
                'unit_number': instance.unit_number,
                'bedrooms': instance.bedrooms,
                'bathrooms': instance.bathrooms
            }
        )


@receiver(post_save, sender=TenantApplication)
def log_application(sender, instance, created, **kwargs):
    """Log when a tenant application is created or updated"""
    if created:
        # User activity for tenant
        UserActivity.objects.create(
            user=instance.tenant,
            activity_type='APPLICATION',
            description=f'Applied for property: {instance.property.title}',
            related_object_type='application',
            related_object_id=str(instance.id),
            data={
                'property_id': str(instance.property.id),
                'unit_id': str(instance.unit.id) if instance.unit else None,
                'status': instance.status
            }
        )
        
        # Analytics metric - applications count
        AnalyticsMetric.objects.create(
            metric_type='APPLICATIONS',
            owner=instance.property.owner,
            property=instance.property,
            count=1,
            date=timezone.now().date(),
            metadata={
                'tenant_id': str(instance.tenant.id),
                'status': instance.status
            }
        )
    else:
        # Log status changes
        UserActivity.objects.create(
            user=instance.tenant,
            activity_type='UPDATE',
            description=f'Application for {instance.property.title} is now {instance.get_status_display()}',
            related_object_type='application',
            related_object_id=str(instance.id),
            data={
                'status': instance.status,
                'previous_status': kwargs.get('previous_status', '')
            }
        )


@receiver(post_save, sender=Lease)
def log_lease_creation(sender, instance, created, **kwargs):
    """Log when a lease is created"""
    if created:
        UserActivity.objects.create(
            user=instance.tenant,
            activity_type='CREATE',
            description=f'Lease created for {instance.property.title}',
            related_object_type='lease',
            related_object_id=str(instance.id),
            data={
                'property_id': str(instance.property.id),
                'unit_id': str(instance.unit.id) if instance.unit else None,
                'monthly_rent': float(instance.monthly_rent),
                'start_date': instance.start_date.isoformat(),
                'end_date': instance.end_date.isoformat()
            }
        )
        
        # Analytics metric - tenant count
        AnalyticsMetric.objects.create(
            metric_type='TENANTS',
            owner=instance.property.owner,
            property=instance.property,
            count=1,
            date=timezone.now().date(),
            metadata={
                'tenant_id': str(instance.tenant.id),
                'lease_id': str(instance.id)
            }
        )


@receiver(post_save, sender=Payment)
def log_payment(sender, instance, created, **kwargs):
    """Log when a payment is created or updated"""
    if created:
        # User activity for payer
        UserActivity.objects.create(
            user=instance.payer,
            activity_type='PAYMENT',
            description=f'Payment of KES {instance.amount:,.2f} initiated',
            related_object_type='payment',
            related_object_id=str(instance.id),
            data={
                'amount': float(instance.amount),
                'payment_type': instance.payment_type,
                'property_id': str(instance.property.id) if instance.property else None,
                'status': instance.status
            }
        )
        
        # Analytics metric - revenue
        if instance.status == 'COMPLETED' and instance.property:
            AnalyticsMetric.objects.create(
                metric_type='REVENUE',
                owner=instance.property.owner,
                property=instance.property,
                value=instance.amount,
                count=1,
                date=timezone.now().date(),
                metadata={
                    'payment_type': instance.payment_type,
                    'payment_id': str(instance.id),
                    'payer_id': str(instance.payer.id)
                }
            )
            
            # Also log platform fee
            platform_fee = instance.amount * Decimal('0.03')
            AnalyticsMetric.objects.create(
                metric_type='REVENUE',
                owner=instance.property.owner,
                property=instance.property,
                value=platform_fee,
                count=0,
                date=timezone.now().date(),
                metadata={
                    'payment_type': 'PLATFORM_FEE',
                    'payment_id': str(instance.id),
                    'original_amount': float(instance.amount)
                }
            )
    else:
        # Log status changes (e.g., from PENDING to COMPLETED)
        if instance.status == 'COMPLETED':
            UserActivity.objects.create(
                user=instance.payer,
                activity_type='PAYMENT',
                description=f'Payment of KES {instance.amount:,.2f} completed',
                related_object_type='payment',
                related_object_id=str(instance.id),
                data={
                    'amount': float(instance.amount),
                    'payment_type': instance.payment_type,
                    'status': instance.status
                }
            )


@receiver(post_save, sender=MaintenanceRequest)
def log_maintenance(sender, instance, created, **kwargs):
    """Log when a maintenance request is created or updated"""
    if created:
        UserActivity.objects.create(
            user=instance.tenant,
            activity_type='MAINTENANCE',
            description=f'Maintenance request: {instance.title}',
            related_object_type='maintenance',
            related_object_id=str(instance.id),
            data={
                'property_id': str(instance.property.id),
                'category': instance.category,
                'priority': instance.priority,
                'status': instance.status
            }
        )
        
        # Analytics metric - maintenance count
        AnalyticsMetric.objects.create(
            metric_type='MAINTENANCE',
            owner=instance.property.owner,
            property=instance.property,
            count=1,
            date=timezone.now().date(),
            metadata={
                'category': instance.category,
                'priority': instance.priority,
                'tenant_id': str(instance.tenant.id)
            }
        )
    else:
        # Log status updates
        if 'status' in kwargs.get('update_fields', []):
            UserActivity.objects.create(
                user=instance.tenant,
                activity_type='MAINTENANCE',
                description=f'Maintenance request {instance.title} is now {instance.get_status_display()}',
                related_object_type='maintenance',
                related_object_id=str(instance.id),
                data={
                    'status': instance.status,
                    'resolved_at': instance.resolved_at.isoformat() if instance.resolved_at else None
                }
            )


@receiver(post_save, sender=PropertyImage)
def log_image_upload(sender, instance, created, **kwargs):
    """Log when property images are uploaded"""
    if created:
        UserActivity.objects.create(
            user=instance.property.owner.user,
            activity_type='CREATE',
            description=f'Uploaded image for {instance.property.title}',
            related_object_type='property_image',
            related_object_id=str(instance.id),
            data={
                'property_id': str(instance.property.id),
                'is_main': instance.is_main
            }
        )


# ========================================
# ANALYTICS METRIC AGGREGATION SIGNALS
# ========================================

@receiver(post_save, sender=TenantApplication)
def update_owner_tenant_count(sender, instance, created, **kwargs):
    """Update owner's tenant count when application is approved"""
    if instance.status == 'APPROVED' and created:
        owner = instance.property.owner
        owner.total_tenants = TenantApplication.objects.filter(
            property__owner=owner,
            status='APPROVED'
        ).values('tenant').distinct().count()
        owner.save()


@receiver(post_save, sender=Payment)
def update_owner_revenue(sender, instance, created, **kwargs):
    """Update owner's total revenue when payment is completed"""
    if instance.status == 'COMPLETED' and instance.property:
        owner = instance.property.owner
        owner.total_revenue = Payment.objects.filter(
            property__owner=owner,
            status='COMPLETED'
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        owner.save()


@receiver(post_save, sender=Unit)
def update_property_unit_count(sender, instance, created, **kwargs):
    """Update property's unit count when units are added"""
    if created:
        property_obj = instance.property_obj
        property_obj.total_units = property_obj.units.count()
        property_obj.available_units = property_obj.units.filter(is_available=True).count()
        property_obj.save()


@receiver(post_save, sender=Lease)
def update_unit_status(sender, instance, created, **kwargs):
    """Update unit status when lease is created"""
    if created and instance.unit:
        instance.unit.status = 'BOOKED'
        instance.unit.is_available = False
        instance.unit.current_tenant = instance.tenant
        instance.unit.save()


# ========================================
# DAILY ANALYTICS AGGREGATION
# ========================================

from django.db import models
from datetime import datetime, timedelta

def aggregate_daily_metrics():
    """Function to aggregate daily analytics metrics"""
    today = timezone.now().date()
    
    # Aggregate property views
    view_count = UserActivity.objects.filter(
        activity_type='VIEW',
        related_object_type='property',
        created_at__date=today
    ).count()
    
    if view_count > 0:
        AnalyticsMetric.objects.create(
            metric_type='PROPERTY_VIEWS',
            count=view_count,
            date=today,
            metadata={'source': 'daily_aggregation'}
        )
    
    # Aggregate applications
    app_count = TenantApplication.objects.filter(
        created_at__date=today
    ).count()
    
    if app_count > 0:
        AnalyticsMetric.objects.create(
            metric_type='APPLICATIONS',
            count=app_count,
            date=today,
            metadata={'source': 'daily_aggregation'}
        )
    
    # Aggregate payments
    payment_total = Payment.objects.filter(
        status='COMPLETED',
        paid_at__date=today
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    if payment_total > 0:
        AnalyticsMetric.objects.create(
            metric_type='REVENUE',
            value=payment_total,
            date=today,
            metadata={'source': 'daily_aggregation'}
        )
    
    # Aggregate maintenance
    maintenance_count = MaintenanceRequest.objects.filter(
        created_at__date=today
    ).count()
    
    if maintenance_count > 0:
        AnalyticsMetric.objects.create(
            metric_type='MAINTENANCE',
            count=maintenance_count,
            date=today,
            metadata={'source': 'daily_aggregation'}
        )