from django.urls import path

from .views import NotificationList, NotificationMarkRead, NotificationPublish

app_name = "notifications"

urlpatterns = [
    path("", NotificationList.as_view(), name="list"),
    path("publish/", NotificationPublish.as_view(), name="publish"),
    path("<int:pk>/read/", NotificationMarkRead.as_view(), name="mark-read"),
]
