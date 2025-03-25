
from datetime import timedelta, timezone
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import F, Sum

from .models import DutyStatus

def validate_70_hour_rule(trip):
    eight_days_ago = timezone.now() - timedelta(days=8)
    driving_hours = DutyStatus.objects.filter(
        log__trip=trip,
        status='D',
        start_time__gte=eight_days_ago
    ).annotate(
        duration=F('end_time') - F('start_time')
    ).aggregate(
        total=Sum('duration')
    )['total']
    
    if driving_hours and driving_hours.total_seconds() / 3600 > 70:
        raise ValidationError("70-hour driving limit exceeded")

def validate_daily_driving(trip):
    for log in trip.daily_logs.all():
        daily_driving = log.duty_status_changes.filter(status='D').aggregate(
            total=Sum(F('end_time') - F('start_time'))
        )['total']
        if daily_driving and daily_driving.total_seconds() / 3600 > 11:
            raise ValidationError(f"Daily driving limit exceeded on {log.date}")