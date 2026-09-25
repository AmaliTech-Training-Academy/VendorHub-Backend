
from django.urls import path

from orders.apis import OrderCreateApi


app_name = "orders"

urlpatterns = [
    path("", OrderCreateApi.as_view(), name="order-create"),
]
