from django.urls import path


from django.urls import path
from .views import VendorListView

urlpatterns = [
    path('', VendorListView.as_view(), name='vendor-list'),
]
