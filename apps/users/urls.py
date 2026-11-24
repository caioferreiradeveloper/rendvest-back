# Django imports
from django.urls import path

# App imports
from apps.users.views import (
    AdminDashboard,
    AdminMessageDetail,
    AdminMessageList,
    AdminUserList,
    AdminUserStatus,
    ContactMessageCreate,
    CurrentUserDetail,
    ExternalUserCreate,
)

# URL configuration for the user app
app_name = "users"


# URL patterns for the user app
urlpatterns = [
    path("contact/", ContactMessageCreate.as_view(), name="contact-create"),
    path("admin/dashboard/", AdminDashboard.as_view(), name="admin-dashboard"),
    path("admin/messages/", AdminMessageList.as_view(), name="admin-messages"),
    path("admin/messages/<int:pk>/", AdminMessageDetail.as_view(), name="admin-message"),
    path("admin/", AdminUserList.as_view(), name="admin-users"),
    path("admin/<uuid:pk>/status/", AdminUserStatus.as_view(), name="admin-user-status"),
    path("external-create/", ExternalUserCreate.as_view(), name="external-user-create"),
    path("current/", CurrentUserDetail.as_view(), name="current-user-detail"),
]
