from django.contrib import admin

from .models import ContactGroup, FieldDefinition, Member, SavedView, TariffBracket, TrainingMode, UserListPreference


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("member_id", "last_name", "first_name", "profile", "status", "city")
    list_filter = ("profile", "status", "groups")
    search_fields = ("first_name", "last_name", "member_id", "email")
    exclude = ("avs_number",)  # donnée sensible : édition uniquement via la fiche applicative


admin.site.register(ContactGroup)
admin.site.register(TrainingMode)
admin.site.register(TariffBracket)
admin.site.register(FieldDefinition)
admin.site.register(SavedView)
admin.site.register(UserListPreference)
