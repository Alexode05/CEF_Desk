from django.contrib import admin

from .models import EmailLog, Invoice, InvoiceBatch, Tariff


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "member", "season", "amount", "status", "issue_date", "due_date")
    list_filter = ("status", "season")
    search_fields = ("number", "member__last_name", "member__first_name")


admin.site.register(InvoiceBatch)
admin.site.register(Tariff)
admin.site.register(EmailLog)
