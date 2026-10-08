"""
Listes de diffusion automatiques « à facturer » (demande d'Alex du 08.10.2026).

Deux listes système, mises à jour en permanence (rien n'est stocké : la liste est recalculée à
chaque affichage) :

- Inscriptions définitives à facturer : fiches Mineur / Majeur au statut « Actif » (inscription
  validée) qui n'ont pas encore de facture de cotisation ENVOYÉE pour la saison en cours ;
- Cours d'essai à facturer : fiches « Cours d'essai » au statut « Essai » (essai validé) qui n'ont
  pas encore de facture de cours d'essai envoyée.

Dès que la facture du membre est envoyée (ou relancée, ou marquée payée), il sort de la liste.
Une facture seulement générée (pas encore envoyée) ou annulée le laisse dans la liste.
"""
from apps.billing.models import Invoice, InvoiceKind, InvoiceStatus
from apps.members.models import ContactKind, Member, MemberStatus, Profile

# Statuts à partir desquels la facture est considérée comme partie : le membre quitte la liste.
SENT_STATUSES = [InvoiceStatus.ENVOYEE, InvoiceStatus.RELANCEE, InvoiceStatus.PAYEE]

MEMBERSHIP = "MEMBERSHIP"
TRIAL = "TRIAL"

BILLING_LISTS = [
    (
        MEMBERSHIP,
        "Inscriptions définitives à facturer",
        "Automatique : inscriptions validées (Actif) dont la facture de cotisation de la saison n'est pas encore envoyée.",
    ),
    (
        TRIAL,
        "Cours d'essai à facturer",
        "Automatique : cours d'essai validés dont la facture d'essai n'est pas encore envoyée.",
    ),
]


def current_season():
    from apps.dashboard.models import ClubSettings

    return ClubSettings.load().current_season_label()


def memberships_to_invoice(season=None):
    season = season or current_season()
    already_sent = Invoice.objects.filter(kind=InvoiceKind.COTISATION, season=season, status__in=SENT_STATUSES).values("member_id")
    return (
        Member.objects.filter(kind=ContactKind.PERSONNE, profile__in=[Profile.MINEUR, Profile.MAJEUR], status=MemberStatus.ACTIF)
        .exclude(pk__in=already_sent)
        .order_by("last_name", "first_name")
    )


def trials_to_invoice():
    # Un cours d'essai ne se facture qu'une fois par fiche : une facture d'essai envoyée, quelle que soit la saison, suffit.
    already_sent = Invoice.objects.filter(kind=InvoiceKind.ESSAI, status__in=SENT_STATUSES).values("member_id")
    return (
        Member.objects.filter(kind=ContactKind.PERSONNE, profile=Profile.ESSAI, status=MemberStatus.ESSAI)
        .exclude(pk__in=already_sent)
        .order_by("last_name", "first_name")
    )


def members_for_rule(rule):
    if rule == MEMBERSHIP:
        return memberships_to_invoice()
    if rule == TRIAL:
        return trials_to_invoice()
    return Member.objects.none()


def list_name_for(member):
    """Nom de la liste « à facturer » dans laquelle un contact validé apparaît (pour l'informer à la validation)."""
    rule = TRIAL if member.profile == Profile.ESSAI else MEMBERSHIP
    return next(name for code, name, _ in BILLING_LISTS if code == rule)


def ensure_billing_lists():
    """Crée les deux listes système si elles manquent (idempotent)."""
    from .models import MailingList

    for rule, name, description in BILLING_LISTS:
        if MailingList.objects.filter(kind=MailingList.Kind.BILLING, billing_rule=rule).exists():
            continue
        final_name = name
        if MailingList.objects.filter(name__iexact=name).exists():
            final_name = f"{name} (automatique)"
        MailingList.objects.create(name=final_name, kind=MailingList.Kind.BILLING, billing_rule=rule, description=description)
