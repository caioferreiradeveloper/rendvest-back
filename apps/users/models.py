# Utility imports
import uuid

# Django imports
from django.contrib.auth.models import AbstractUser
from django.db import models

# App imports
from apps.users.managers import UserManager


# Custom user model that uses email authentication and UUID as the primary key
class User(AbstractUser):
    username = None
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("e-mail", unique=True)

    pending_approval = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        
        # Defines the default ordering of users by email
        ordering = ["email"]

    # Returns the user's email as their string representation
    def __str__(self):
        return self.email


class ContactMessage(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    message = models.TextField(max_length=5000)
    monthly_goal = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    preferred_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notification = models.OneToOneField(
        "notifications.Notification",
        related_name="contact_message",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at", "-pk"]
