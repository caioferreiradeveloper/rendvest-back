from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    class Type(models.TextChoices):
        SYSTEM = "system", "Sistema"
        ALERT = "alert", "Alerta"
        NEWS = "news", "Notícia"

    title = models.CharField(max_length=160)
    description = models.TextField()
    date = models.DateTimeField(default=timezone.now, db_index=True)
    type = models.CharField(max_length=10, choices=Type.choices)
    staff_only = models.BooleanField(default=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    class Meta:
        ordering = ("-date", "-pk")


class NotificationRead(models.Model):
    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="read_receipts"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("notification", "user"), name="unique_notification_read_by_user"
            )
        ]
