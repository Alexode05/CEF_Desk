from django.urls import path

from . import views

app_name = "exports"

urlpatterns = [
    path("contacts/", views.export_members, name="members"),
    path("factures/", views.export_invoices, name="invoices"),
]
