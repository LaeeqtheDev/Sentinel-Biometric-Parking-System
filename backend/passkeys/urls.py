from django.urls import path

from . import views

urlpatterns = [
    # WebAuthn registration
    path("register/options/", views.register_options, name="webauthn_register_options"),
    path("register/verify/", views.register_verify, name="webauthn_register_verify"),
    # WebAuthn authentication
    path("auth/options/", views.auth_options, name="webauthn_auth_options"),
    path("auth/verify/", views.auth_verify, name="webauthn_auth_verify"),
    # Credential management
    path("my/", views.my_credentials, name="webauthn_my_credentials"),
    path(
        "credentials/<int:credential_id>/",
        views.delete_credential,
        name="webauthn_delete_credential",
    ),
    # Pickup tokens
    path(
        "pickup-tokens/",
        views.create_pickup_token,
        name="pickup_token_create",
    ),
    path(
        "pickup-tokens/<str:token>/",
        views.get_pickup_token,
        name="pickup_token_get",
    ),
    path(
        "pickup-tokens/<str:token>/authorize/",
        views.authorize_pickup_token,
        name="pickup_token_authorize",
    ),
]
