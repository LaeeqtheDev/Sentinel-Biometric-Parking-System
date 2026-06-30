from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"", views.VehicleViewSet, basename="vehicles")

urlpatterns = [
    path("detect-plate/", views.detect_plate, name="detect_plate"),
    path("my/", views.my_vehicles, name="my_vehicles"),
    path("my/add/", views.add_my_vehicle, name="add_my_vehicle"),
    path("my/<int:vehicle_id>/", views.remove_my_vehicle, name="remove_my_vehicle"),
    path("my/<int:vehicle_id>/doc/", views.upload_vehicle_doc, name="upload_vehicle_doc"),
    path("walk-up/", views.walk_up_register, name="walk_up_register"),
    path("pending-approvals/", views.pending_approvals, name="pending_approvals"),
    path("pending-documents/", views.pending_documents, name="pending_documents"),
    path("", include(router.urls)),
]
