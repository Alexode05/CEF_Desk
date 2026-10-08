"""Logique du passage de saison : invitations, réponses des membres, traitement par le comité."""
import logging

from django.core.mail import EmailMessage
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.billing.models import EmailLog
from apps.dashboard.models import ClubSettings
from apps.members import services as member_services
from apps.members.models import ContactKind, Member, MemberStatus

from .forms import apply_proposed
from .models import RenewalRequest, SeasonRollover

logger = logging.getLogger(__name__)
Status = RenewalRequest.Status

DEV_LINKS_SESSION_KEY = "cef_dev_renewal_links"


class RenewalError(Exception):
    pass


def season_choices():
    current = ClubSettings.load().current_season_label()
    end = int(current.split("-")[1])
    following = f"{end}-{end + 1}"
    return [(following, f"{following} (saison suivante)"), (current, f"{current} (saison en cours)")]


def eligible_members():
    """Membres actifs (personnes) : ceux qui reçoivent l'invitation."""
    return Member.objects.filter(kind=ContactKind.PERSONNE, status=MemberStatus.ACTIF).order_by("last_name", "first_name")


def _render(text, values):
    try:
        return text.format(**values)
    except (KeyError, IndexError, ValueError):
        return text


def send_invitation(request, req, token):
    """Envoie (ou renvoie) l'email d'invitation ; renvoie le lien personnel."""
    rollover = req.rollover
    link = request.build_absolute_uri(reverse("renewals:public_form", args=[token]))
    member = req.member
    values = {
        "prenom": member.first_name, "nom": member.last_name, "saison": rollover.target_season,
        "lien": link, "date_limite": timezone.localtime(req.expires_at).strftime("%d.%m.%Y"),
    }
    subject, body = _render(rollover.subject, values), _render(rollover.body, values)
    log = EmailLog(kind="mailing", to=req.email, subject=subject, member=member, sent_by=request.user if request.user.is_authenticated else None)
    try:
        EmailMessage(subject=subject, body=body, to=[req.email]).send(fail_silently=False)
    except Exception as exc:  # noqa: BLE001
        log.ok, log.error = False, str(exc)
        log.save()
        req.status, req.send_error = Status.FAILED, str(exc)
        req.save()
        raise RenewalError(f"{req.member_name} : échec d'envoi ({exc}).") from exc
    log.save()
    req.status, req.send_error, req.sent_at = Status.SENT, "", timezone.now()
    req.save()
    return link


def launch(request, target_season, subject, body, members):
    """
    Envoie l'invitation à chaque membre sélectionné. Un seul passage par saison : relancer pour la même
    saison n'invite que les membres qui ne l'ont pas encore été (ex. devenus actifs entre-temps).
    """
    rollover, _ = SeasonRollover.objects.get_or_create(target_season=target_season, defaults={"subject": subject, "body": body})
    rollover.subject, rollover.body = subject, body
    rollover.created_by = rollover.created_by or request.user
    rollover.save()

    report = {"sent": 0, "failed": [], "skipped": 0, "links": []}
    already = set(rollover.requests.exclude(status=Status.FAILED).values_list("member_id", flat=True))
    for member in members:
        if member.pk in already:
            report["skipped"] += 1
            continue
        req = rollover.requests.filter(member=member).first() or RenewalRequest(rollover=rollover, member=member)
        req.member_name, req.email = member.display_name, member.primary_email or ""
        token = req.new_token()
        if not req.email:
            req.status, req.send_error = Status.FAILED, "Aucune adresse email sur la fiche."
            req.save()
            report["failed"].append(f"{member.display_name} : aucune adresse email sur la fiche.")
            continue
        req.save()
        try:
            report["links"].append((member.display_name, send_invitation(request, req, token)))
            report["sent"] += 1
        except RenewalError as exc:
            report["failed"].append(str(exc))
    return rollover, report


def resend(request, req):
    if req.member is None or req.status not in (Status.SENT, Status.FAILED):
        raise RenewalError("Cette invitation a déjà reçu une réponse.")
    req.email = req.member.primary_email or ""
    if not req.email:
        raise RenewalError(f"{req.member_name} : aucune adresse email sur la fiche.")
    token = req.new_token()  # l'ancien lien cesse de fonctionner
    req.save()
    return send_invitation(request, req, token)


# --- Réponses des membres ------------------------------------------------------------------------


def submit_update(request, req, form):
    proposed, changes = form.diff()
    req.proposed, req.changes = proposed, changes
    req.remark = form.cleaned_data.get("remark", "")
    req.status, req.responded_at = Status.TO_VALIDATE, timezone.now()
    req.save()
    _notify(request, req)


def submit_resignation(request, req, remark):
    req.remark = (remark or "").strip()[:2000]
    req.status, req.responded_at = Status.RESIGNATION, timezone.now()
    req.save()
    _notify(request, req)


def _notify(request, req):
    """Email au secrétariat, comme pour une inscription."""
    club = ClubSettings.load()
    to = club.secretariat_email
    if not to:
        return
    review_url = request.build_absolute_uri(reverse("renewals:review", args=[req.pk]))
    season = req.rollover.target_season
    if req.status == Status.RESIGNATION:
        subject = f"[CEF Desk] Passage de saison {season} — démission annoncée : {req.member_name}"
        lines = [f"{req.member_name} annonce sa démission du club pour la saison {season}.", ""]
        lines += [f"Motif / remarque : {req.remark}" if req.remark else "Aucune remarque.", ""]
        lines += ["La fiche n'est PAS encore supprimée : confirmez la démission dans CEF Desk.", review_url]
    else:
        subject = f"[CEF Desk] Passage de saison {season} — données à valider : {req.member_name}"
        lines = [f"{req.member_name} a vérifié ses données pour la saison {season}.", ""]
        if req.changes:
            lines.append("Modifications demandées :")
            for c in req.changes:
                new = "nouvelle valeur saisie (voir CEF Desk)" if c.get("sensitive") else c["new"]
                old = "valeur actuelle masquée" if c.get("sensitive") else c["old"]
                lines.append(f"- {c['label']} : {old} → {new}")
        else:
            lines.append("Aucune modification : les données actuelles sont confirmées.")
        if req.remark:
            lines += ["", f"Remarque : {req.remark}"]
        lines += ["", "Les modifications ne sont appliquées à la fiche qu'après validation dans CEF Desk :", review_url]
    log = EmailLog(kind="notification", to=to, subject=subject, member=req.member)
    try:
        EmailMessage(subject=subject, body="\n".join(lines), to=[to]).send(fail_silently=False)
    except Exception as exc:  # noqa: BLE001 — la réponse est enregistrée quoi qu'il arrive
        logger.exception("Notification du secrétariat impossible")
        log.ok, log.error = False, str(exc)
    log.save()


# --- Traitement par le comité ---------------------------------------------------------------------


@transaction.atomic
def validate(req, user, billing):
    if req.status != Status.TO_VALIDATE or req.member is None:
        raise RenewalError("Cette réponse n'est pas (ou plus) à valider.")
    member = req.member
    apply_proposed(member, req.proposed)
    member.refresh_from_db()
    if billing.get("training_mode") is not None:
        member.training_mode = billing["training_mode"]
    member.tariff_bracket = billing["tariff_bracket"]
    member.family_discount = billing.get("family_discount", False)
    member.save()
    req.status, req.processed_at, req.processed_by = Status.VALIDATED, timezone.now(), user
    req.save()
    return member


@transaction.atomic
def confirm_resignation(req, user):
    if req.status != Status.RESIGNATION:
        raise RenewalError("Aucune démission à confirmer pour cette réponse.")
    kept = 0
    if req.member is not None:
        try:
            kept = member_services.delete_member_keep_invoices(req.member)
        except member_services.MemberDeletionError as exc:
            raise RenewalError(str(exc)) from exc
    req.member = None
    req.proposed, req.changes = {}, []  # plus aucune donnée personnelle inutile
    req.status, req.processed_at, req.processed_by = Status.RESIGNED, timezone.now(), user
    req.save()
    return kept


def keep_member(req, user):
    if req.status != Status.RESIGNATION:
        raise RenewalError("Aucune démission à traiter pour cette réponse.")
    req.status, req.processed_at, req.processed_by = Status.KEPT, timezone.now(), user
    req.save()
