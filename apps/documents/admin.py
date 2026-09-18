from django.contrib import admin

from .models import Folder, StoredFile

admin.site.register(Folder)
admin.site.register(StoredFile)
