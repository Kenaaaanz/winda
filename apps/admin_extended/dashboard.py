from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce, TruncDate, TruncMonth
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
CHART_COLORS = ('#167348', '#b38b2e', '#278f5a', '#76664a', '#54b982')
EVENT_PERIODS = {
    '7d': 7,
    '30d': 30,
    '90d': 90,
    '365d': 365,
}


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


def _bucket_date(value):
    if hasattr(value, 'date'):
        value = value.date()
    return value.replace(day=1) if value.day != 1 else value


def _month_starts(start, end):
    current = start.replace(day=1)
    last = end.replace(day=1)
    months = []
    while current <= last:
        months.append(current)
        current = (
            current.replace(year=current.year + 1, month=1)
            if current.month == 12
            else current.replace(month=current.month + 1)
        )
    return months


def _event_chart(values, labels):
    maximum = max((max(series['values'], default=0) for series in values), default=0)
    maximum = max(maximum, 1)
    series_data = []
    for series_index, series in enumerate(values):
        coordinates = []
        points = []
        for index, count in enumerate(series['values']):
            x = round(index * CHART_WIDTH / max(len(labels) - 1, 1))
            y = round(CHART_BOTTOM - count / maximum * (CHART_BOTTOM - CHART_TOP))
            coordinates.append(f'{x},{y}')
            points.append({'x': x, 'y': y, 'count': count, 'label': labels[index]})
        series_data.append({
            'label': series['label'],
            'color': CHART_COLORS[series_index % len(CHART_COLORS)],
            'line': ' '.join(coordinates),
            'points': points,
        })
    return series_data


def event_analytics_context(period='30d'):
    today = timezone.localdate()
    period = period if period in (*EVENT_PERIODS, 'all') else '30d'
    monthly = period == 'all'
    events = AnalyticsEvent.objects.all()

    if monthly:
        first_event = events.order_by('created_at').values_list('created_at', flat=True).first()
        start = timezone.localtime(first_event).date() if first_event else today
        bucket_dates = _month_starts(start, today)
        bucket_expression = TruncMonth('created_at')
    else:
        start = today - timedelta(days=EVENT_PERIODS[period] - 1)
        bucket_dates = [
            start + timedelta(days=offset)
            for offset in range(EVENT_PERIODS[period])
        ]
        bucket_expression = TruncDate('created_at')
        events = events.filter(created_at__date__range=(start, today))

    grouped = list(
        events.annotate(bucket=bucket_expression)
        .values('bucket', 'event_type')
        .annotate(total=Count('id'))
    )
    bucket_counts = {}
    type_totals = {}
    for row in grouped:
        bucket = _bucket_date(row['bucket'])
        event_type = row['event_type']
        bucket_counts[(bucket, event_type)] = row['total']
        type_totals[event_type] = type_totals.get(event_type, 0) + row['total']

    event_choices = dict(AnalyticsEvent.EVENT_TYPES)
    sorted_types = sorted(type_totals, key=type_totals.get, reverse=True)
    top_types = sorted_types[:5]
    labels = [day.strftime('%b %Y' if monthly else '%d %b') for day in bucket_dates]
    totals_by_bucket = [
        sum(bucket_counts.get((day, event_type), 0) for event_type in type_totals)
        for day in bucket_dates
    ]
    trend_series = _event_chart(
        [
            {'label': event_choices.get(event_type, event_type), 'values': [
                bucket_counts.get((day, event_type), 0) for day in bucket_dates
            ]}
            for event_type in top_types
        ],
        labels,
    )
    overall_trend = _event_chart(
        [{'label': 'All events', 'values': totals_by_bucket}],
        labels,
    )
    event_total = sum(type_totals.values())
    event_mix = []
    pie_stops = []
    boundary = 0
    for index, event_type in enumerate(sorted_types):
        count = type_totals[event_type]
        if not count:
            continue
        end = boundary + count * 100 / max(event_total, 1)
        color = CHART_COLORS[index % len(CHART_COLORS)]
        event_mix.append({
            'label': event_choices.get(event_type, event_type.replace('_', ' ').title()),
            'count': count,
            'percentage': round(count * 100 / max(event_total, 1), 1),
            'color': color,
        })
        pie_stops.append(f'{color} {boundary:.2f}% {end:.2f}%')
        boundary = end

    recent_events = events.filter(
        created_at__gte=timezone.now() - timedelta(minutes=15)
    ).count()
    today_events = AnalyticsEvent.objects.filter(created_at__date=today).count()
    users = events.exclude(user_id=None).values('user_id').distinct().count()
    sessions = events.exclude(session_id='').values('session_id').distinct().count()
    bar_max = max(type_totals.values(), default=1)
    bars = [
        {
            'label': event_choices.get(event_type, event_type.replace('_', ' ').title()),
            'count': count,
            'width': round(count * 100 / max(bar_max, 1)),
        }
        for event_type, count in sorted(type_totals.items(), key=lambda item: item[1], reverse=True)
    ]

    return {
        'period': period,
        'period_label': 'All recorded history' if monthly else f'Last {EVENT_PERIODS[period]} days',
        'period_options': [
            {'value': '7d', 'label': '7 days'},
            {'value': '30d', 'label': '30 days'},
            {'value': '90d', 'label': '90 days'},
            {'value': '365d', 'label': '12 months'},
            {'value': 'all', 'label': 'All history'},
        ],
        'total': event_total,
        'events_today': today_events,
        'events_last_15_minutes': recent_events,
        'unique_users': users,
        'unique_sessions': sessions,
        'top_event': event_mix[0] if event_mix else None,
        'event_mix': event_mix,
        'pie_style': f"conic-gradient({', '.join(pie_stops)})" if pie_stops else '#e8ddc8',
        'event_bars': bars,
        'trend_series': trend_series,
        'overall_trend': overall_trend,
        'chart_labels': [
            labels[index]
            for index in sorted(
                set((0, len(labels) // 4, len(labels) // 2, 3 * len(labels) // 4, len(labels) - 1))
            )
        ] if labels else [],
        'recent_activity': events.select_related('user', 'property').order_by('-created_at')[:12],
        'period_start': start,
        'period_end': today,
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

    completed_payments = Payment.objects.filter(status='COMPLETED')
    dated_completed_payments = completed_payments.annotate(
        settled_at=Coalesce('paid_at', 'updated_at', 'created_at')
    )
    recent_completed_payments = dated_completed_payments.filter(
        settled_at__date__range=date_range
    )
    revenue_by_day = {
        row['day']: row['total'] or Decimal('0')
        for row in recent_completed_payments.annotate(day=TruncDate('settled_at'))
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

    recent_completed_count = recent_completed_payments.count()
    recent_failed_payments = Payment.objects.filter(status='FAILED').annotate(
        settled_at=Coalesce('updated_at', 'created_at')
    ).filter(settled_at__date__range=date_range)
    failed_count = recent_failed_payments.count()
    completed_count = recent_completed_count
    lifetime_volume = completed_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    lifetime_platform_fees = completed_payments.aggregate(
        total=Sum('platform_fee') + Sum('building_subscription_fee')
    )['total'] or Decimal('0')
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
                'label': 'Lifetime payment volume',
                'value': lifetime_volume,
                'detail': f"{completed_payments.count():,} completed payments · all time",
                'tone': 'green',
                'currency': True,
            },
            {
                'label': 'Lifetime platform fees',
                'value': lifetime_platform_fees,
                'detail': 'Collected from completed payments · all time',
                'tone': 'blue',
                'currency': True,
            },
            {
                'label': 'Completed payments',
                'value': completed_payments.count(),
                'detail': f'{recent_completed_count:,} completed in the last 30 days',
                'tone': 'green',
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
