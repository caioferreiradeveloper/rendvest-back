# Django imports
from django.apps import AppConfig


# Wishlist app configuration
class WishlistConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.wishlist"
    label = "wishlist"
