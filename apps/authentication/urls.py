# Django imports
from django.urls import path

# App imports
from apps.authentication.views import CsrfTokenAuth, LoginAuth, LogoutAuth, RefreshAuth

# URL configuration for the authentication app
app_name = "authentication"


# URL patterns for the authentication app
urlpatterns = [
    path("csrf/", CsrfTokenAuth.as_view(), name="csrf-token-auth"),
    path("login/", LoginAuth.as_view(), name="login-auth"),
    path("refresh/", RefreshAuth.as_view(), name="refresh-auth"),
    path("logout/", LogoutAuth.as_view(), name="logout-auth"),
]
