from django.urls import path

from orders.apis import OrderCreateApi, OrderStatusUpdateApi


app_name = "orders"

urlpatterns = [
    path("", OrderCreateApi.as_view(), name="order-create"),
    path(
        "<int:order_id>/status/",
        OrderStatusUpdateApi.as_view(),
        name="order-status-update",
    ),
]
