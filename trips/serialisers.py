from rest_framework import serializers
from .models import DailyLog, DutyStatus, Trip, LogSheet

class TripSerializer(serializers.ModelSerializer):

    stops = serializers.SerializerMethodField()
    fuel_stops = serializers.SerializerMethodField()
    class Meta:
        model = Trip
        fields = '__all__'
        extra_kwargs = {
            'distance_miles': {'required': True},
            'pickup_location': {'required': True}
        }

    def get_stops(self, obj):
        return obj.route_data.get('stops', [])

    def get_fuel_stops(self, obj):
        return obj.route_data.get('fuel_stops', [])

class LogSheetSerializer(serializers.ModelSerializer):
    class Meta:
        model = LogSheet
        fields = '__all__'

class DutyStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = DutyStatus
        fields = ['status', 'start_time', 'end_time', 'duration_hours']

class DailyLogSerializer(serializers.ModelSerializer):
    duty_status_changes = DutyStatusSerializer(many=True, read_only=True)

    class Meta:
        model = DailyLog 
        fields = '__all__'
    
class Meta:
    model = DailyLog
    fields = ['id', 'date', 'driver_name', 'total_miles_driven', 'remarks', 'duty_status_changes']