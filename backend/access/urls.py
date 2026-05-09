from django.urls import path

from . import views

urlpatterns = [
    path("logs/", views.AccessLogList.as_view(), name="access_logs"),
    path("stats/", views.stats, name="access_stats"),
    path("verify-entry/", views.verify_entry, name="verify_entry"),
    path("verify-exit/", views.verify_exit, name="verify_exit"),
    path("live-detect/", views.live_detect, name="live_detect"),
    path("manual-override/", views.manual_override, name="manual_override"),
    path("risk-events/", views.risk_events, name="risk_events"),
]
