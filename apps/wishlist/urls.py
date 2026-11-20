from django.urls import path

from apps.wishlist.views import (
    WishlistItemCreate,
    WishlistItemDelete,
    WishlistItemDetail,
    WishlistItemList,
    WishlistItemUpdate,
)

app_name = "wishlist"

urlpatterns = [
    path("", WishlistItemList.as_view(), name="item-list"),
    path("create/", WishlistItemCreate.as_view(), name="item-create"),
    path("<uuid:pk>/", WishlistItemDetail.as_view(), name="item-detail"),
    path("update/<uuid:pk>/", WishlistItemUpdate.as_view(), name="item-update"),
    path("delete/<uuid:pk>/", WishlistItemDelete.as_view(), name="item-delete"),
]
