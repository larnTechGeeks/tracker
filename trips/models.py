
from datetime import date, datetime, timedelta, timezone
from django.db import models
from django.forms import ValidationError
from django.utils import timezone

class Trip(models.Model):
    current_location = models.CharField(max_length=255)
    pickup_location = models.CharField(max_length=255)
    dropoff_location = models.CharField(max_length=255)
    current_cycle_used = models.FloatField()  # in hours
    created_at = models.DateTimeField(auto_now_add=True)
    distance_miles = models.FloatField(null=True, blank=True)
    route_data = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Trip from {self.pickup_location} to {self.dropoff_location}"

class LogSheet(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='log_sheets')
    date = models.DateField()
    driving_hours = models.FloatField()
    rest_hours = models.FloatField()
    fueling_stops = models.IntegerField(default=0)

    def __str__(self):
        return f"Log Sheet for {self.trip} on {self.date}"

class DailyLog(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='daily_logs')  # Link to Trip
    date = models.DateField()
    driver_name = models.CharField(max_length=100)
    total_miles_driven = models.FloatField(default=0)
    remarks = models.TextField(blank=True)

class DutyStatus(models.Model):

    STATUS_CHOICES = [
        ('OFF', 'Off Duty'),
        ('SB', 'Sleeper Berth'),
        ('D', 'Driving'),
        ('ON', 'On Duty')
    ]

    log = models.ForeignKey(DailyLog, related_name='duty_status_changes', on_delete=models.CASCADE)
    status = models.CharField(max_length=20)
    start_time = models.TimeField()
    end_time = models.TimeField()
    coordinates = models.CharField(max_length=50, blank=True, null=True)  # stores "lon,lat"
    duration_hours = models.FloatField(null=True, blank=True)
    distance = models.FloatField(null=True)

    def clean(self):
        # Validate 70-hour/8-day rule
        if self.status == 'D':
            # Get the 8-day window
            eight_days_ago = timezone.now() - timedelta(days=8)
            
            # Calculate total driving hours in the past 8 days
            driving_periods = DutyStatus.objects.filter(
                log__trip=self.log.trip,
                status='D',
                start_time__gte=eight_days_ago
            ).exclude(id=self.id)  # Exclude current instance if updating
            
            total_seconds = 0
            today = date.today()
            for status in driving_periods:
                start_dt = datetime.combine(today, status.start_time)
                end_dt = datetime.combine(today, status.end_time)
                # If the period crosses midnight, adjust end_dt by adding one day.
                if end_dt < start_dt:
                    end_dt += timedelta(days=1)
                total_seconds += (end_dt - start_dt).total_seconds()
            
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    # def save(self, *args, **kwargs):
    #     # Auto-calculate duration if not provided
    #     if not self.duration_hours and self.start_time and self.end_time:
    #         start = datetime.datetime.combine(datetime.date.today(), self.start_time)
    #         end = datetime.datetime.combine(datetime.date.today(), self.end_time)
    #         self.duration_hours = (end - start).total_seconds() / 3600
    #     super().save(*args, **kwargs)