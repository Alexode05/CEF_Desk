from django.urls import path

from . import views

app_name = "formbuilder"

urlpatterns = [path("", views.form_list, name="list")]
