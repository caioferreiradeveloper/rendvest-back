from rest_framework import generics

from apps.wishlist.models import WishlistItem
from apps.wishlist.serializers import WishlistItemSerializer


class WishlistItemMixin:
    serializer_class = WishlistItemSerializer
    queryset = WishlistItem.objects.none()

    def get_queryset(self):
        return WishlistItem.objects.filter(user=self.request.user)


class WishlistItemList(WishlistItemMixin, generics.ListAPIView):
    ordering_fields = ["name", "amount", "expected_purchase_date", "created_at"]


class WishlistItemCreate(WishlistItemMixin, generics.CreateAPIView):
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WishlistItemDetail(WishlistItemMixin, generics.RetrieveAPIView):
    pass


class WishlistItemUpdate(WishlistItemMixin, generics.UpdateAPIView):
    pass


class WishlistItemDelete(WishlistItemMixin, generics.DestroyAPIView):
    pass
