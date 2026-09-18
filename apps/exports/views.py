from django.http import HttpResponse


def export_members(request):
    return HttpResponse("Export à venir", content_type="text/plain")
