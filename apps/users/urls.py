from django.urls import path

from apps.users.views import CurrentUserView, RegisterView

app_name = "users"

urlpatterns = [
    path("", RegisterView.as_view(), name="register"),
    path("me/", CurrentUserView.as_view(), name="me"),
]
