from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("", views.index, name="index"),
    path("factures/", views.invoice_list, name="invoice_list"),
    path("factures/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("factures/nouvelle/<int:member_pk>/", views.invoice_create, name="invoice_create"),
    path("bareme/", views.tariffs, name="tariffs"),
    path("bareme.json", views.tariff_grid_json, name="tariff_grid_json"),
]
