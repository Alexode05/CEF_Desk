"""
Export CSV — cahier des charges section 10.

Trois variantes, différant par séparateur / encodage / fin de ligne :
  - excel   : Excel Windows, iOS, Android  -> UTF-8 avec BOM, « ; », CRLF
  - macos   : Excel macOS                  -> UTF-8 (sans BOM), « ; », LF
  - numbers : Apple Numbers                -> UTF-8 (sans BOM), « , », LF
Le N° AVS (et tout champ marqué sensible) est exclu sauf sélection explicite de sa colonne.
"""
import csv
import io
from datetime import date

from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST

from apps.billing.models import Invoice
from apps.members import fields as F
from apps.members.models import Member

VARIANTS = {
    "excel": {"delimiter": ";", "encoding": "utf-8-sig", "lineterminator": "\r\n", "label": "Excel-Windows"},
    "macos": {"delimiter": ";", "encoding": "utf-8", "lineterminator": "\n", "label": "macOS"},
    "numbers": {"delimiter": ",", "encoding": "utf-8", "lineterminator": "\n", "label": "Numbers"},
}


def build_csv(headers, rows, variant):
    spec = VARIANTS[variant]
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=spec["delimiter"], lineterminator=spec["lineterminator"], quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode(spec["encoding"])


def csv_response(filename_base, headers, rows, variant):
    if variant not in VARIANTS:
        return HttpResponseBadRequest("Format inconnu")
    payload = build_csv(headers, rows, variant)
    filename = f"{filename_base}_{VARIANTS[variant]['label']}_{date.today():%Y-%m-%d}.csv"
    response = HttpResponse(payload, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@require_POST
def export_members(request):
    ids = [int(x) for x in request.POST.get("ids", "").split(",") if x.strip().isdigit()]
    members = list(Member.objects.filter(pk__in=ids).select_related("training_mode", "tariff_bracket").prefetch_related("groups"))
    if not members:
        return HttpResponseBadRequest("Aucun contact sélectionné")

    defs = F.all_field_definitions()
    mode = request.POST.get("column_mode", "all")
    if mode == "custom":
        wanted = set(request.POST.getlist("columns"))
        columns = [d for d in defs if d.key in wanted]  # sensibles inclus uniquement si cochés
    else:
        columns = [d for d in defs if not d.is_sensitive]  # jamais l'AVS par défaut
        if mode == "filled":
            columns = [d for d in columns if any(F.display_value(m, d.key) for m in members)]

    headers = [d.label for d in columns]
    rows = [[F.display_value(m, d.key) for d in columns] for m in members]
    return csv_response("contacts", headers, rows, request.POST.get("variant", "excel"))


@require_POST
def export_invoices(request):
    ids = [int(x) for x in request.POST.get("ids", "").split(",") if x.strip().isdigit()]
    qs = Invoice.objects.select_related("member")
    invoices = qs.filter(pk__in=ids) if ids else qs
    headers = ["N°", "Membre", "Saison", "Modalité", "Tranche", "Montant de base", "Réduction famille", "Montant", "Émise le", "Échéance", "Statut", "Envoyée le", "Relances", "Payée le", "Référence", "Email"]
    rows = [
        [
            i.number, i.member.display_name, i.season, i.training_mode_label, i.bracket_label,
            f"{i.base_amount:.2f}", f"{i.family_discount:.2f}", f"{i.amount:.2f}",
            i.issue_date.strftime("%d.%m.%Y"), i.due_date.strftime("%d.%m.%Y"), i.get_status_display(),
            i.sent_at.strftime("%d.%m.%Y") if i.sent_at else "", i.reminder_count,
            i.paid_at.strftime("%d.%m.%Y") if i.paid_at else "", i.reference, i.recipient_email,
        ]
        for i in invoices
    ]
    return csv_response("factures", headers, rows, request.POST.get("variant", "excel"))
