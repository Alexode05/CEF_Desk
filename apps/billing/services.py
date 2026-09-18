"""
Logique métier de facturation : création d'une facture pour un membre, numérotation,
référence de paiement (calculée par python-stdnum, jamais à la main), PDF + archivage,
envoi email (Cc trésorier), relances, validation du paiement.
"""
from datetime import timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone
from stdnum import iso11649
from stdnum.ch import esr

from apps.dashboard.models import ClubSettings
from apps.documents.services import store_generated_file
from apps.members import services as member_services
from apps.members.models import Member

from .models import EmailLog, Invoice, InvoiceBatch, InvoiceStatus
from .pdf import render_invoice_pdf


class BillingError(Exception):
    pass


# --- Numérotation et références -------------------------------------------


def next_invoice_number(season_end_year):
    prefix = f"{season_end_year}-"
    last = Invoice.objects.filter(number__startswith=prefix).order_by("-number").values_list("number", flat=True).first()
    seq = int(last.split("-")[1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def make_reference(club, invoice_pk, season_end_year):
    """
    QR-IBAN  -> référence QR (27 chiffres, contrôle modulo 10 récursif via stdnum.ch.esr)
    IBAN     -> référence SCOR ISO 11649 (RF + 2 chiffres de contrôle + 21 caractères max)
    """
    if club.is_qr_iban:
        base = f"{season_end_year:04d}{invoice_pk:022d}"[-26:]
        return base + esr.calc_check_digit(base)
    body = f"{season_end_year:04d}{invoice_pk:012d}"
    check = iso11649.mod_97_10.calc_check_digits(body + "RF")
    ref = f"RF{check}{body}"
    iso11649.validate(ref)
    return ref


# --- Création ---------------------------------------------------------------


def invoice_description(member, season):
    parts = [f"Cotisation saison {season}", member.display_name]
    if member.training_mode:
        parts.append(str(member.training_mode))
    return " - ".join(parts)[:140]


@transaction.atomic
def create_invoice_for_member(member: Member, user=None, batch: InvoiceBatch = None, season=None, issue_date=None):
    club = ClubSettings.load()
    season = season or club.current_season_label()
    season_end_year = int(season.split("-")[1])
    issue_date = issue_date or timezone.localdate()

    base = member.base_tariff
    if base is None:
        raise BillingError(
            f"{member.display_name} : montant introuvable (modalité d'entraînement ou tranche tarifaire manquante, "
            "ou tarif non défini dans le barème)."
        )
    discount = member_services.FAMILY_DISCOUNT_CHF if member.family_discount else Decimal("0.00")
    amount = member_services.compute_contribution(base, member.family_discount)
    if amount is None or amount <= 0:
        raise BillingError(f"{member.display_name} : montant calculé nul ou négatif.")

    if Invoice.objects.filter(member=member, season=season).exclude(status=InvoiceStatus.ANNULEE).exists():
        raise BillingError(f"{member.display_name} : une facture existe déjà pour la saison {season}.")

    invoice = Invoice(
        number=next_invoice_number(season_end_year),
        member=member,
        batch=batch,
        season=season,
        training_mode_label=str(member.training_mode) if member.training_mode else "",
        bracket_label=str(member.tariff_bracket) if member.tariff_bracket else "",
        base_amount=base,
        family_discount=discount,
        amount=amount,
        description=invoice_description(member, season),
        debtor_name=member.display_name[:70],
        debtor_street=member.address[:70],
        debtor_postal_code=member.postal_code[:16],
        debtor_city=member.city[:35],
        debtor_country=member.country or "CH",
        recipient_email=member.primary_email or "",
        issue_date=issue_date,
        due_date=issue_date + timedelta(days=club.invoice_due_days),
        created_by=user,
    )
    invoice.save()
    invoice.reference = make_reference(club, invoice.pk, season_end_year)
    invoice.save(update_fields=["reference"])
    generate_pdf(invoice, user=user)
    return invoice


def generate_pdf(invoice: Invoice, user=None):
    """(Re)génère le PDF, l'attache à la facture et l'archive dans Club/Factures/<saison>/."""
    club = ClubSettings.load()
    pdf_bytes = render_invoice_pdf(club, invoice)
    filename = f"Facture_{invoice.number}_{member_services._ascii_slug(invoice.member.display_name)}.pdf"
    if invoice.pdf:
        invoice.pdf.delete(save=False)
    invoice.pdf.save(filename, ContentFile(pdf_bytes), save=False)
    stored = store_generated_file(f"Club/Factures/{invoice.season}", filename, pdf_bytes, "application/pdf", user=user)
    invoice.archived_file = stored
    invoice.save(update_fields=["pdf", "archived_file"])
    return pdf_bytes


# --- Envoi ------------------------------------------------------------------


def _render_template(text, invoice):
    club = ClubSettings.load()
    values = {
        "saison": invoice.season,
        "prenom": invoice.member.first_name,
        "nom": invoice.member.last_name,
        "modalite": invoice.training_mode_label or "—",
        "montant": f"{invoice.amount:.2f}",
        "echeance": invoice.due_date.strftime("%d.%m.%Y"),
        "numero": invoice.number,
        "club": club.club_name,
    }
    try:
        return text.format(**values)
    except (KeyError, IndexError, ValueError):
        return text


def send_invoice_email(invoice: Invoice, user=None, reminder=False):
    """Envoie la facture (ou la relance) par email, PDF joint, trésorier en Cc."""
    club = ClubSettings.load()
    to = invoice.recipient_email or invoice.member.primary_email
    if not to:
        raise BillingError(f"{invoice.member.display_name} : aucune adresse email sur la fiche.")
    if not invoice.pdf:
        generate_pdf(invoice, user=user)

    subject_tpl = club.reminder_email_subject if reminder else club.invoice_email_subject
    body_tpl = club.reminder_email_body if reminder else club.invoice_email_body
    subject = _render_template(subject_tpl, invoice)
    body = _render_template(body_tpl, invoice)
    cc = [club.treasurer_email] if club.treasurer_email else []

    msg = EmailMessage(subject=subject, body=body, to=[to], cc=cc)
    invoice.pdf.open("rb")
    try:
        msg.attach(invoice.pdf.name.split("/")[-1], invoice.pdf.read(), "application/pdf")
    finally:
        invoice.pdf.close()

    log = EmailLog(kind="relance" if reminder else "facture", to=to, cc=", ".join(cc), subject=subject, invoice=invoice, member=invoice.member, sent_by=user)
    try:
        msg.send(fail_silently=False)
    except Exception as exc:  # noqa: BLE001
        log.ok, log.error = False, str(exc)
        log.save()
        raise BillingError(f"{invoice.member.display_name} : échec d'envoi ({exc}).") from exc
    log.save()

    now = timezone.now()
    if reminder:
        invoice.status = InvoiceStatus.RELANCEE
        invoice.reminded_at = now
        invoice.reminder_count += 1
        invoice.save(update_fields=["status", "reminded_at", "reminder_count"])
    else:
        if invoice.status == InvoiceStatus.GENEREE:
            invoice.status = InvoiceStatus.ENVOYEE
        invoice.sent_at = invoice.sent_at or now
        invoice.save(update_fields=["status", "sent_at"])
    return log


def mark_paid(invoice: Invoice, user=None, paid_on=None):
    invoice.status = InvoiceStatus.PAYEE
    invoice.paid_at = paid_on or timezone.localdate()
    invoice.paid_marked_by = user
    invoice.save(update_fields=["status", "paid_at", "paid_marked_by"])


def unmark_paid(invoice: Invoice):
    invoice.status = InvoiceStatus.RELANCEE if invoice.reminder_count else (InvoiceStatus.ENVOYEE if invoice.sent_at else InvoiceStatus.GENEREE)
    invoice.paid_at = None
    invoice.paid_marked_by = None
    invoice.save(update_fields=["status", "paid_at", "paid_marked_by"])


def run_due_reminders(user=None):
    """Envoie les relances dues (facture envoyée, impayée, délai écoulé). Renvoie (envoyées, erreurs)."""
    sent, errors = [], []
    for inv in Invoice.objects.sent().select_related("member"):
        if inv.reminder_is_due:
            try:
                send_invoice_email(inv, user=user, reminder=True)
                sent.append(inv)
            except BillingError as exc:
                errors.append(str(exc))
    return sent, errors


# --- Lots -------------------------------------------------------------------


@transaction.atomic
def create_batch(members, label, user=None, source_description=""):
    club = ClubSettings.load()
    season = club.current_season_label()
    batch = InvoiceBatch.objects.create(label=label, season=season, created_by=user, source_description=source_description)
    created, errors = [], []
    for m in members:
        try:
            with transaction.atomic():
                created.append(create_invoice_for_member(m, user=user, batch=batch, season=season))
        except BillingError as exc:
            errors.append(str(exc))
    return batch, created, errors


def send_batch(batch: InvoiceBatch, user=None, only_ids=None):
    sent, errors = [], []
    qs = batch.invoices.filter(status=InvoiceStatus.GENEREE).select_related("member")
    if only_ids is not None:
        qs = qs.filter(pk__in=only_ids)
    for inv in qs:
        try:
            send_invoice_email(inv, user=user)
            sent.append(inv)
        except BillingError as exc:
            errors.append(str(exc))
    return sent, errors
