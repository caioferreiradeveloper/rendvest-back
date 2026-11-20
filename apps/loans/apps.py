# Django imports
from django.apps import AppConfig


# Loans app configuration
class LoansConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.loans"
    label = "loans"
