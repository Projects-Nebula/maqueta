from django.urls import path

from .views import (
    AnalyticsCollectView,
    AnalyticsConsentView,
    AnalyticsHeatmapView,
    AnalyticsOverviewView,
    AnalyticsSessionsView,
)

urlpatterns = [
    path("consent/", AnalyticsConsentView.as_view(), name="consent"),
    path("collect/", AnalyticsCollectView.as_view(), name="collect"),
    path("overview/", AnalyticsOverviewView.as_view(), name="overview"),
    path("sessions/", AnalyticsSessionsView.as_view(), name="sessions"),
    path("heatmap/", AnalyticsHeatmapView.as_view(), name="heatmap"),
]
