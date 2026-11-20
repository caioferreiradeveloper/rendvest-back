# Django imports
from django.contrib.auth.base_user import BaseUserManager


# Class manager responsible for creating and managing user accounts
class UserManager(BaseUserManager):
    use_in_migrations = True

    # Creates and saves a regular user with a normalized email and encrypted password
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    # Creates and saves a superuser with administrative privileges
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superusuários precisam ter is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superusuários precisam ter is_superuser=True.")
        return self.create_user(email, password, **extra_fields)
