from django.contrib import admin

from .models import AccountProfile

admin.site.site_header = "CEF Desk — administration technique"
admin.site.site_title = "CEF Desk"
admin.site.index_title = "Administration"


@admin.register(AccountProfile)
class AccountProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "email_verified_at")
    search_fields = ("user__username", "user__email")
