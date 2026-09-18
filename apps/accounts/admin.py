from django.contrib import admin
from django.contrib.admin import AdminSite
from django_otp.admin import OTPAdminSite

# L'admin Django exige aussi l'A2F (django-otp).
admin.site.__class__ = OTPAdminSite
admin.site.site_header = "CEF Desk — administration technique"
admin.site.site_title = "CEF Desk"
admin.site.index_title = "Administration"
