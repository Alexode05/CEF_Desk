from django.contrib import admin

from .models import FormDefinition, FormField, FormSubmission


class FormFieldInline(admin.TabularInline):
    model = FormField
    extra = 0
    fk_name = "form"


@admin.register(FormDefinition)
class FormDefinitionAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "profile", "is_active")
    inlines = [FormFieldInline]


admin.site.register(FormSubmission)
