from django.shortcuts import render


def index(request):
    return render(request, "placeholder.html", {"title": "Module en cours de développement"})
