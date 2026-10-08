from django.contrib import admin

from .models import RenewalRequest, SeasonRollover


class RenewalRequestInline(admin.TabularInline):
    model = RenewalRequest
    extra = 0
    fields = ("member_name", "email", "status", "sent_at", "responded_at", "processed_at")
    readonly_fields = fields
    can_delete = False


@admin.register(SeasonRollover)
class SeasonRolloverAdmin(admin.ModelAdmin):
    list_display = ("target_season", "created_at", "created_by")
    inlines = [RenewalRequestInline]
