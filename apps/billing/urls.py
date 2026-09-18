from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("", views.index, name="index"),
    path("factures/", views.invoice_list, name="invoice_list"),
    path("factures/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("factures/<int:pk>/pdf/", views.invoice_pdf, name="invoice_pdf"),
    path("factures/<int:pk>/envoyer/", views.invoice_send, name="invoice_send"),
    path("factures/<int:pk>/regenerer/", views.invoice_regenerate, name="invoice_regenerate"),
    path("factures/<int:pk>/payee/", views.invoice_toggle_paid, name="invoice_toggle_paid"),
    path("factures/<int:pk>/annuler/", views.invoice_cancel, name="invoice_cancel"),
    path("factures/nouvelle/<int:member_pk>/", views.invoice_create, name="invoice_create"),
    path("lots/", views.batch_list, name="batch_list"),
    path("lots/nouveau/", views.batch_create, name="batch_create"),
    path("lots/<int:pk>/", views.batch_detail, name="batch_detail"),
    path("lots/<int:pk>/envoyer/", views.batch_send, name="batch_send"),
    path("relances/executer/", views.run_reminders, name="run_reminders"),
    path("bareme/", views.tariffs, name="tariffs"),
    path("bareme.json", views.tariff_grid_json, name="tariff_grid_json"),
]
