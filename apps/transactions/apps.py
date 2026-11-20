# Django imports
from django.apps import AppConfig


# Transactions app configuration
class TransactionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.transactions"
    label = "transactions"
