from django.urls import path

from orders.apis import (
    OrderCreateApi,
    OrderListApi,
    OrderStatusUpdateApi,
)

app_name = "orders"

urlpatterns = [
    path("", OrderCreateApi.as_view(), name="order-create"),
    path("list/", OrderListApi.as_view(), name="order-list"),
    path(
        "<int:order_id>/status/",
        OrderStatusUpdateApi.as_view(),
        name="order-status-update",
    ),
]