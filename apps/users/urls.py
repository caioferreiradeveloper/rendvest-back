# Django imports
from django.urls import path

# App imports
from apps.users.views import ExternalUserCreate, CurrentUserDetail

# URL configuration for the user app
app_name = "users"


# URL patterns for the user app
urlpatterns = [
    path("external-create/", ExternalUserCreate.as_view(), name="external-user-create"),
    path("current/", CurrentUserDetail.as_view(), name="current-user-detail"),
]
