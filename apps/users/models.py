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

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        
        # Defines the default ordering of users by email
        ordering = ["email"]

    # Returns the user's email as their string representation
    def __str__(self):
        return self.email
