# Django imports
from django.apps import AppConfig


# Debtors app configuration
class DebtorsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.debtors"
    label = "debtors"
