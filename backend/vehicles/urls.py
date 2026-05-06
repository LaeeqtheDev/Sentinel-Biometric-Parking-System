from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"", views.VehicleViewSet, basename="vehicles")

urlpatterns = [
    path("detect-plate/", views.detect_plate, name="detect_plate"),
    path("my/", views.my_vehicles, name="my_vehicles"),
    path("", include(router.urls)),
]
