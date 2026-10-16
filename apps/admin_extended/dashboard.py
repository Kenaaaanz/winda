from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.accounts.models import User
from apps.analytics.models import AnalyticsEvent
from apps.communications.models import Message
from apps.payments.models import Payment
from apps.properties.models import Property
from apps.tenants.models import TenantApplication


CHART_WIDTH = 720
CHART_TOP = 24
CHART_BOTTOM = 190


def _make_chart(values, dates, value_format='number'):
    maximum = max(max(values, default=0), 1)
    points = []
    coordinates = []

    for index, (value, day) in enumerate(zip(values, dates)):
        x = round(index * CHART_WIDTH / max(len(values) - 1, 1))
        y = round(CHART_BOTTOM - value / maximum * (CHART_BOTTOM - CHART_TOP))
        coordinates.append(f'{x},{y}')
        display_value = (
            f'KES {value:,.2f}' if value_format == 'currency' else f'{value:,}'
        )
        points.append({
            'x': x,
            'y': y,
            'label': day.strftime('%d %b'),
            'value': display_value,
        })

    return {
        'line': ' '.join(coordinates),
        'area': f'0,{CHART_BOTTOM} {" ".join(coordinates)} {CHART_WIDTH},{CHART_BOTTOM}',
        'points': points,
        'max': maximum,
    }


def dashboard_callback(request, context):
    if not request.user.is_superuser:
        return context

    today = timezone.localdate()
    first_day = today - timedelta(days=29)
    days = [first_day + timedelta(days=offset) for offset in range(30)]
    date_range = (first_day, today)

    event_queryset = AnalyticsEvent.objects.filter(created_at__date__range=date_range)
    event_counts = {
        row['day']: row['total']
        for row in event_queryset.annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total=Count('id'))
    }
    daily_events = [event_counts.get(day, 0) for day in days]

    completed_payments = Payment.objects.filter(
        status='COMPLETED',
        paid_at__date__range=date_range,
    )
    revenue_by_day = {
        row['day']: row['total'] or Decimal('0')
        for row in completed_payments.annotate(day=TruncDate('paid_at'))
        .values('day')
        .annotate(total=Sum('amount'))
    }
    daily_revenue = [float(revenue_by_day.get(day, 0)) for day in days]

    recent_events = (
        event_queryset.select_related('user', 'property')
        .order_by('-created_at')[:8]
    )
    event_labels = dict(AnalyticsEvent.EVENT_TYPES)
    top_events = [
        {
            'label': event_labels.get(row['event_type'], row['event_type'].replace('_', ' ').title()),
            'count': row['total'],
            'percentage': round(row['total'] * 100 / max(sum(daily_events), 1)),
        }
        for row in event_queryset.values('event_type')
        .annotate(total=Count('id'))
        .order_by('-total')[:6]
    ]

    completed_count = Payment.objects.filter(
        status='COMPLETED',
        created_at__date__range=date_range,
    ).count()
    failed_count = Payment.objects.filter(
        status='FAILED',
        created_at__date__range=date_range,
    ).count()
    resolved_payment_count = completed_count + failed_count
    payment_success_rate = round(
        completed_count * 100 / resolved_payment_count
    ) if resolved_payment_count else 0

    context['dashboard'] = {
        'period_label': f'{first_day:%d %b} – {today:%d %b %Y}',
        'cards': [
            {
                'label': 'Total users',
                'value': User.objects.count(),
                'detail': f"{User.objects.filter(date_joined__date__range=date_range).count():,} joined in 30 days",
                'tone': 'green',
            },
            {
                'label': 'Active users',
                'value': event_queryset.exclude(user_id=None).values('user_id').distinct().count(),
                'detail': 'Tracked activity in 30 days',
                'tone': 'blue',
            },
            {
                'label': 'Properties',
                'value': Property.objects.count(),
                'detail': f"{Property.objects.filter(verification_status='VERIFIED').count():,} verified",
                'tone': 'amber',
            },
            {
                'label': 'Tracked events',
                'value': sum(daily_events),
                'detail': f"{event_queryset.filter(created_at__date=today).count():,} today",
                'tone': 'violet',
            },
            {
                'label': 'Payment volume',
                'value': completed_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0'),
                'detail': 'Completed payments · 30 days',
                'tone': 'green',
                'currency': True,
            },
            {
                'label': 'Platform fees',
                'value': completed_payments.aggregate(
                    total=Sum('platform_fee') + Sum('building_subscription_fee')
                )['total'] or Decimal('0'),
                'detail': 'Fees collected · 30 days',
                'tone': 'blue',
                'currency': True,
            },
            {
                'label': 'Applications to review',
                'value': TenantApplication.objects.filter(
                    status__in=('PENDING', 'UNDER_REVIEW')
                ).count(),
                'detail': 'Pending or under review',
                'tone': 'amber',
            },
            {
                'label': 'Payment success',
                'value': f'{payment_success_rate}%',
                'detail': f'{completed_count:,} completed · {failed_count:,} failed',
                'tone': 'violet',
            },
        ],
        'events_chart': _make_chart(daily_events, days),
        'revenue_chart': _make_chart(daily_revenue, days, value_format='currency'),
        'chart_labels': [
            days[index].strftime('%d %b')
            for index in (0, 7, 14, 21, 29)
        ],
        'top_events': top_events,
        'recent_events': recent_events,
        'engagement': {
            'messages': Message.objects.filter(
                is_deleted=False,
                created_at__date__range=date_range,
            ).count(),
            'property_views': event_queryset.filter(event_type='PROPERTY_VIEW').count(),
            'searches': event_queryset.filter(event_type='SEARCH').count(),
            'registrations': event_queryset.filter(event_type='USER_REGISTER').count(),
        },
        'health': {
            'pending_properties': Property.objects.filter(
                verification_status='PENDING'
            ).count(),
            'pending_applications': TenantApplication.objects.filter(
                status='PENDING'
            ).count(),
            'failed_payments': failed_count,
            'active_users': User.objects.filter(is_active=True).count(),
        },
    }
    return context
