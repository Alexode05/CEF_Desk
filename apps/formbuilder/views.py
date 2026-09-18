from django.shortcuts import render


def form_list(request):
    return render(request, "placeholder.html", {"title": "Formulaires"})
