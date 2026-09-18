from django.contrib import admin

from .models import Campaign, MailingList

admin.site.register(MailingList)
admin.site.register(Campaign)
