from django.urls import path

from . import views, policy_views

urlpatterns = [
    path("sessions/", views.ParkingSessionList.as_view(), name="parking_sessions"),
    path("sessions/active/", views.active_sessions, name="parking_active_sessions"),
    path("my/", views.my_sessions, name="my_parking_sessions"),
    path(
        "active-for/<str:plate>/",
        views.active_for_plate,
        name="parking_active_for_plate",
    ),
    path("policy/", policy_views.policy_config, name="policy_config"),
]
