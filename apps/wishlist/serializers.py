from rest_framework import serializers

from apps.wishlist.models import WishlistItem


class WishlistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = WishlistItem
        fields = ["id", "name", "amount", "expected_purchase_date", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
