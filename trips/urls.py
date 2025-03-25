from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CalculateRouteView, GenerateLogSheetsView, TripViewSet, LogSheetViewSet

router = DefaultRouter()
router.register(r'trips', TripViewSet, basename='trip')
router.register(r'logsheets', LogSheetViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('calculate-route/', CalculateRouteView.as_view(), name='calculate_route'),
    path('generate-log-sheets/<int:trip_id>/', GenerateLogSheetsView.as_view(), name='generate_log_sheets'),
]