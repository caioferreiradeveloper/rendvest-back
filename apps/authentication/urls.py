from django.urls import path

from apps.authentication.views import CsrfTokenView, LoginView, LogoutView, RefreshView

app_name = "authentication"

urlpatterns = [
    path("csrf/", CsrfTokenView.as_view(), name="csrf"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshView.as_view(), name="refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
