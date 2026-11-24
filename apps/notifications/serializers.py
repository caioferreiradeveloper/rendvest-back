from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    contact_message_id = serializers.IntegerField(
        source="contact_message.pk", read_only=True, allow_null=True
    )

    class Meta:
        model = Notification
        fields = ("id", "title", "description", "date", "type", "status", "contact_message_id")

    @extend_schema_field(serializers.ChoiceField(choices=("read", "no_read")))
    def get_status(self, notification):
        return "read" if notification.is_read else "no_read"


class NotificationPublishSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ("id", "title", "description", "date", "type", "recipient")
