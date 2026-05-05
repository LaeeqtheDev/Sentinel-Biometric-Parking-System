from django.urls import path

from . import views

urlpatterns = [
    path("logs/", views.AccessLogList.as_view(), name="access_logs"),
    path("stats/", views.stats, name="access_stats"),
    path("verify-entry/", views.verify_entry, name="verify_entry"),
]
