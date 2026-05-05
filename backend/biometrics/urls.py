from django.urls import path

from . import views

urlpatterns = [
    path("enroll/", views.enroll, name="biometric_enroll"),
    path("verify/", views.verify, name="biometric_verify"),
    path("profile/<int:user_id>/", views.profile_detail, name="biometric_profile"),
]
