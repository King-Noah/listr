from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    # path("search_addresses/", views.search_addresses, name="search_addresses"),
    path("search_proximity/", views.search_proximity, name="search_proximity"),
]