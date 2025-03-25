from argparse import Action
from datetime import timedelta
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.exceptions import ValidationError
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .utils import calculate_route, generate_daily_logs
from .models import LogSheet, Trip, DailyLog, DutyStatus
from .serialisers import LogSheetSerializer, TripSerializer, DailyLogSerializer, DutyStatusSerializer
from .validators import validate_70_hour_rule, validate_daily_driving

class TripViewSet(viewsets.ModelViewSet):
    queryset = Trip.objects.all()
    serializer_class = TripSerializer

    @action(detail=True, methods=['get'])   
    def daily_logs(self, request, pk=None):
        """Get all logs for a trip."""
        trip = self.get_object()
        logs = DailyLog.objects.filter(trip=trip).select_related('trip').prefetch_related('duty_status_changes')
        if not logs.exists():
            return Response({"detail": "No logs found for this trip"}, status=404)
        serializer = DailyLogSerializer(logs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def route_details(self, request, pk=None):
        """
        Custom action to retrieve route details, including stops, rests, and fueling locations.
        """
        trip = self.get_object()
        pickup = trip.pickup_location
        dropoff = trip.dropoff_location
        
        route_data = calculate_route(pickup, dropoff)
        if not route_data:
            return Response({"error": "Faileeed to calculate route"}, status=500)
        
        print(route_data)          
        return Response(route_data)
    
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)       

        route_data = calculate_route(
            request.data.get('pickup_location'),
            request.data.get('dropoff_location')
        )

        if not route_data:
            return Response({"error": "Failed to calculate route"}, status=400)
        
        trip = serializer.save(
            distance_miles=route_data['distance_miles'],
            route_data=route_data 
        )

        generate_daily_logs(trip, route_data)

        try:
            validate_70_hour_rule(trip)
            validate_daily_driving(trip)
        except ValidationError as e:
            trip.delete()
            return Response({"error": str(e)}, status=400)
        
        return Response({
            **serializer.data,
            'stops': route_data['stops'],
            'fuel_stops': route_data['fuel_stops']
        }, status=201)

class LogSheetViewSet(viewsets.ModelViewSet):
    queryset = LogSheet.objects.all()
    serializer_class = LogSheetSerializer

class CalculateRouteView(View):
    def get(self, request):
        pickup = request.GET.get("pickup")
        dropoff = request.GET.get("dropoff")
        if not pickup or not dropoff:
            return JsonResponse({"error": "Both pickup and dropoff locations are required.Ensure they are provided"}, status=400)

        route_data = calculate_route(pickup, dropoff)
        if not route_data:
            return JsonResponse({"error": "Failed to calculate route view"}, status=500)

        return JsonResponse(route_data)

@method_decorator(csrf_exempt, name='dispatch')
class GenerateLogSheetsView(View):
    @csrf_exempt 
    def post(self, request, trip_id):
        try:
            trip = Trip.objects.get(id=trip_id)
        except Trip.DoesNotExist:
            return JsonResponse({"error": "Trip not found"}, status=404)

        generate_log_sheets(trip)
        return JsonResponse({"status": "Log sheets generated successfully"})

def generate_log_sheets(trip):
    driving_hours_per_day = 11  # Max driving hours per day
    total_hours = trip.current_cycle_used
    days = int(total_hours // driving_hours_per_day)
    remaining_hours = total_hours % driving_hours_per_day

    for day in range(days + 1):
        LogSheet.objects.create(
            trip=trip,
            date=trip.created_at.date() + timedelta(days=day),
            driving_hours=driving_hours_per_day if day < days else remaining_hours,
            rest_hours=24 - driving_hours_per_day,
            fueling_stops=1 if day % 2 == 0 else 0  # Example logic for fueling stops
        )

