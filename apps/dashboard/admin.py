from django.contrib import admin

from .models import ClubSettings, DashboardNote, TodoItem, TodoLog


@admin.register(ClubSettings)
class ClubSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not ClubSettings.objects.exists()


admin.site.register(DashboardNote)
admin.site.register(TodoItem)
admin.site.register(TodoLog)
