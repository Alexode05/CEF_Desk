from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("compte/", include("apps.accounts.urls")),
    path("", include("apps.dashboard.urls")),
    path("contacts/", include("apps.members.urls")),
    path("comptabilite/", include("apps.billing.urls")),
    path("fichiers/", include("apps.documents.urls")),
    path("formulaires/", include("apps.formbuilder.urls")),
    path("mailing/", include("apps.mailing.urls")),
    path("export/", include("apps.exports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
