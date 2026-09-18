from django.http import JsonResponse
from django.shortcuts import render


def _placeholder(request, title):
    return render(request, "placeholder.html", {"title": title})


def index(request):
    return _placeholder(request, "Comptabilité")


def invoice_list(request):
    return _placeholder(request, "Factures")


def invoice_detail(request, pk):
    return _placeholder(request, "Facture")


def invoice_create(request, member_pk):
    return _placeholder(request, "Nouvelle facture")


def tariffs(request):
    return _placeholder(request, "Barème")


def tariff_grid_json(request):
    from .models import Tariff

    grid = {f"{t.training_mode_id}:{t.bracket_id}": (str(t.amount) if t.amount is not None else None) for t in Tariff.objects.all()}
    return JsonResponse(grid)
