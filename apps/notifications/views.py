from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions
from rest_framework.response import Response

from .models import Notification, NotificationRead
from .serializers import NotificationPublishSerializer, NotificationSerializer


class NotificationMixin:
    serializer_class = NotificationSerializer
    queryset = Notification.objects.none()

    def get_queryset(self):
        user = self.request.user
        queryset = Notification.objects.all()
        if not user.is_staff:
            queryset = queryset.filter(staff_only=False)
        return (
            queryset.select_related("contact_message").filter(date__lte=timezone.now())
            .filter(Q(recipient__isnull=True) | Q(recipient=user))
            .annotate(
                is_read=Exists(
                    NotificationRead.objects.filter(notification=OuterRef("pk"), user=user)
                )
            )
        )


class NotificationList(NotificationMixin, generics.ListAPIView):
    pagination_class = None


class NotificationMarkRead(NotificationMixin, generics.GenericAPIView):
    @extend_schema(request=None, responses=NotificationSerializer)
    def post(self, request, pk):
        notification = self.get_object()
        NotificationRead.objects.get_or_create(notification=notification, user=request.user)
        notification.is_read = True
        return Response(self.get_serializer(notification).data)


class NotificationPublish(generics.CreateAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = NotificationPublishSerializer
