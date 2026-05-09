from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = DefaultRouter()
router.register(r"users", views.UserViewSet, basename="users")

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("register/", views.register, name="register"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", views.me, name="me"),
    path("me/documents/", views.upload_my_documents, name="upload_my_documents"),
    path("change-password/", views.change_password, name="change_password"),
    path("", include(router.urls)),
]
