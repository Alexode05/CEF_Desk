from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import Sum
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.dashboard.models import ClubSettings
from apps.members.models import Member, TariffBracket, TrainingMode

from . import services
from .forms import BatchCreateForm, ManualInvoiceForm, MarkPaidForm
from .models import EmailLog, Invoice, InvoiceBatch, InvoiceStatus, Tariff


def index(request):
    club = ClubSettings.load()
    season = club.current_season_label()
    unpaid = Invoice.objects.unpaid()
    stats = {
        "unpaid_count": unpaid.count(),
        "unpaid_total": unpaid.aggregate(s=Sum("amount"))["s"] or Decimal("0"),
        "overdue_count": sum(1 for i in unpaid if i.is_overdue),
        "paid_season_total": Invoice.objects.filter(season=season, status=InvoiceStatus.PAYEE).aggregate(s=Sum("amount"))["s"] or Decimal("0"),
        "paid_season_count": Invoice.objects.filter(season=season, status=InvoiceStatus.PAYEE).count(),
        "reminders_due": sum(1 for i in Invoice.objects.sent() if i.reminder_is_due),
        "undefined_tariffs": Tariff.objects.filter(amount__isnull=True).count(),
    }
    return render(
        request,
        "billing/index.html",
        {
            "club": club,
            "season": season,
            "stats": stats,
            "batches": InvoiceBatch.objects.all()[:8],
            "recent_emails": EmailLog.objects.select_related("member")[:8],
            "recent_unpaid": unpaid.select_related("member").order_by("due_date")[:10],
        },
    )


def invoice_list(request):
    etat = request.GET.get("etat", "impayees")
    season = request.GET.get("saison", "")
    qs = Invoice.objects.select_related("member", "batch")
    if etat == "impayees":
        qs = qs.unpaid()
    elif etat == "payees":
        qs = qs.filter(status=InvoiceStatus.PAYEE)
    elif etat == "relances":
        qs = qs.filter(status=InvoiceStatus.RELANCEE)
    elif etat == "generees":
        qs = qs.filter(status=InvoiceStatus.GENEREE)
    if season:
        qs = qs.filter(season=season)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(member__last_name__icontains=q) | qs.filter(member__first_name__icontains=q) | qs.filter(number__icontains=q)
    seasons = Invoice.objects.order_by("-season").values_list("season", flat=True).distinct()
    return render(
        request,
        "billing/invoice_list.html",
        {
            "invoices": qs,
            "etat": etat,
            "season": season,
            "seasons": seasons,
            "q": q,
            "total": qs.aggregate(s=Sum("amount"))["s"] or Decimal("0"),
            "today": timezone.localdate(),
        },
    )


def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("member", "batch"), pk=pk)
    return render(
        request,
        "billing/invoice_detail.html",
        {"invoice": invoice, "emails": invoice.emails.all(), "paid_form": MarkPaidForm(), "club": ClubSettings.load()},
    )


def invoice_pdf(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if not invoice.pdf:
        services.generate_pdf(invoice, user=request.user)
    try:
        response = FileResponse(invoice.pdf.open("rb"), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{invoice.pdf.name.split("/")[-1]}"'
        return response
    except FileNotFoundError:
        raise Http404("PDF introuvable")


def invoice_create(request, member_pk):
    member = get_object_or_404(Member, pk=member_pk)
    club = ClubSettings.load()
    preview = {
        "season": club.current_season_label(),
        "base": member.base_tariff,
        "discount": member.family_discount,
        "amount": member.computed_amount,
        "email": member.primary_email,
    }
    if request.method == "POST":
        try:
            invoice = services.create_invoice_for_member(member, user=request.user)
        except services.BillingError as exc:
            messages.error(request, str(exc))
            return redirect("billing:invoice_create", member_pk=member.pk)
        messages.success(request, f"Facture {invoice.number} générée et archivée. Vous pouvez la relire puis l'envoyer.")
        return redirect(invoice)
    return render(request, "billing/invoice_create.html", {"member": member, "preview": preview, "club": club})


def invoice_manual(request):
    """Facture indépendante créée à la main : choix du destinataire, montant, motif."""
    initial = {}
    if request.GET.get("member", "").isdigit():
        initial["member"] = int(request.GET["member"])
    form = ManualInvoiceForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            invoice = services.create_manual_invoice(
                data["member"], data["amount"], data["description"], user=request.user,
                issue_date=data["issue_date"], due_date=data["due_date"], recipient_email=data.get("recipient_email", ""),
            )
        except services.BillingError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Facture {invoice.number} créée et archivée. Relisez le PDF puis envoyez-la depuis cette page.")
            return redirect(invoice)
    return render(request, "billing/invoice_manual.html", {"form": form, "club": ClubSettings.load()})


@require_POST
def invoice_send(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    try:
        log = services.send_invoice_email(invoice, user=request.user, reminder=request.POST.get("reminder") == "1")
        messages.success(request, f"Email envoyé à {log.to}{' (Cc ' + log.cc + ')' if log.cc else ''}.")
    except services.BillingError as exc:
        messages.error(request, str(exc))
    return redirect(invoice)


@require_POST
def invoice_regenerate(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    services.generate_pdf(invoice, user=request.user)
    messages.success(request, "PDF régénéré et ré-archivé.")
    return redirect(invoice)


@require_POST
def invoice_toggle_paid(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if invoice.status == InvoiceStatus.PAYEE:
        services.unmark_paid(invoice)
        messages.info(request, f"Facture {invoice.number} remise en attente de paiement.")
    else:
        form = MarkPaidForm(request.POST)
        paid_at = form.cleaned_data.get("paid_at") if form.is_valid() else None
        services.mark_paid(invoice, user=request.user, paid_on=paid_at)
        messages.success(request, f"Facture {invoice.number} marquée payée. Les relances sont arrêtées.")
    return redirect(request.POST.get("next") or invoice.get_absolute_url())


@require_POST
def invoice_cancel(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if invoice.status == InvoiceStatus.PAYEE:
        messages.error(request, "Une facture payée ne peut pas être annulée.")
    else:
        invoice.status = InvoiceStatus.ANNULEE
        invoice.save(update_fields=["status"])
        messages.success(request, f"Facture {invoice.number} annulée.")
    return redirect(invoice)


# --- Barème ------------------------------------------------------------------


def tariffs(request):
    modes = list(TrainingMode.objects.all())
    brackets = list(TariffBracket.objects.all())
    grid = {(t.training_mode_id, t.bracket_id): t for t in Tariff.objects.all()}
    if request.method == "POST":
        errors = 0
        for m in modes:
            for b in brackets:
                raw = request.POST.get(f"t_{m.pk}_{b.pk}", "").strip().replace("'", "").replace(",", ".")
                t = grid.get((m.pk, b.pk)) or Tariff(training_mode=m, bracket=b)
                if raw == "":
                    t.amount = None
                else:
                    try:
                        t.amount = Decimal(raw)
                    except InvalidOperation:
                        errors += 1
                        continue
                t.save()
        if errors:
            messages.warning(request, f"{errors} montant(s) non reconnu(s) ont été ignorés.")
        else:
            messages.success(request, "Barème enregistré. Les tarifs s'affichent désormais sur les fiches membres.")
        return redirect("billing:tariffs")
    rows = [(m, [grid.get((m.pk, b.pk)) for b in brackets]) for m in modes]
    return render(request, "billing/tariffs.html", {"modes": modes, "brackets": brackets, "rows": rows})


def tariff_grid_json(request):
    grid = {f"{t.training_mode_id}:{t.bracket_id}": (str(t.amount) if t.amount is not None else None) for t in Tariff.objects.all()}
    return JsonResponse(grid)


# --- Lots : génération puis envoi groupés -------------------------------------


def batch_list(request):
    return render(request, "billing/batch_list.html", {"batches": InvoiceBatch.objects.prefetch_related("invoices")})


def batch_create(request):
    club = ClubSettings.load()
    initial = {"label": f"Cotisations {club.current_season_label()}"}
    ids = request.GET.get("ids", "")
    if ids:
        initial["ids"] = ids
    if request.GET.get("list"):
        initial["mailing_list"] = request.GET.get("list")
    form = BatchCreateForm(request.POST or None, initial=initial)
    preview = None
    if request.method == "POST" and form.is_valid():
        members = list(form.members())
        if form.cleaned_data.get("skip_already_invoiced"):
            season = club.current_season_label()
            already = set(Invoice.objects.filter(season=season).exclude(status=InvoiceStatus.ANNULEE).values_list("member_id", flat=True))
            members = [m for m in members if m.pk not in already]
        if request.POST.get("confirm") == "1":
            if not members:
                messages.warning(request, "Aucun membre à facturer avec ces critères.")
                return redirect("billing:batch_create")
            source = form.cleaned_data.get("group") or form.cleaned_data.get("mailing_list") or f"{len(members)} contacts sélectionnés"
            batch, created, errors = services.create_batch(members, form.cleaned_data["label"], user=request.user, source_description=str(source))
            messages.success(request, f"{len(created)} facture(s) générée(s) et archivée(s) dans le lot « {batch.label} ». Relisez-les puis envoyez-les.")
            for e in errors:
                messages.warning(request, e)
            return redirect("billing:batch_detail", pk=batch.pk)
        preview = [(m, m.computed_amount, m.primary_email) for m in members]
    return render(request, "billing/batch_create.html", {"form": form, "preview": preview, "club": club})


def batch_detail(request, pk):
    batch = get_object_or_404(InvoiceBatch, pk=pk)
    invoices = batch.invoices.select_related("member")
    return render(
        request,
        "billing/batch_detail.html",
        {
            "batch": batch,
            "invoices": invoices,
            "to_send": invoices.filter(status=InvoiceStatus.GENEREE).count(),
            "club": ClubSettings.load(),
        },
    )


@require_POST
def batch_send(request, pk):
    batch = get_object_or_404(InvoiceBatch, pk=pk)
    only = request.POST.getlist("ids") or None
    sent, errors = services.send_batch(batch, user=request.user, only_ids=only)
    if sent:
        messages.success(request, f"{len(sent)} facture(s) envoyée(s) par email (trésorier en copie).")
    for e in errors:
        messages.warning(request, e)
    return redirect("billing:batch_detail", pk=batch.pk)


@require_POST
def run_reminders(request):
    sent, errors = services.run_due_reminders(user=request.user)
    messages.success(request, f"{len(sent)} relance(s) envoyée(s).") if sent else messages.info(request, "Aucune relance due aujourd'hui.")
    for e in errors:
        messages.warning(request, e)
    return redirect("billing:index")
