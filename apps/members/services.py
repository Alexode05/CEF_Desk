"""
Règles métier du module Contacts : ID automatique, âge, catégorie, montant de cotisation.
"""
import re
import unicodedata
from datetime import date
from decimal import Decimal

FAMILY_DISCOUNT_CHF = Decimal("100.00")

# Catégories d'âge Swiss Fencing : (borne supérieure exclusive de l'âge atteint
# dans l'année de fin de saison, libellé). Sénior = 20-39 ans, Vétéran dès 40.
AGE_CATEGORIES = [
    (8, "U8"),
    (10, "U10"),
    (12, "U12"),
    (14, "U14"),
    (17, "U17"),
    (20, "U20"),
    (40, "Sénior"),
    (999, "Vétéran"),
]
CATEGORY_LABELS = [label for _, label in AGE_CATEGORIES]


def _ascii_slug(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = value.encode("ascii", "ignore").decode("ascii").lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value


def generate_member_id(first_name, last_name, exclude_pk=None, company_name=""):
    """
    `prenom.nom` en minuscules sans accents ; en cas d'homonyme : `prenom.nom2`, `prenom.nom3`…
    """
    from .models import Member

    if company_name and not (first_name or last_name):
        base = _ascii_slug(company_name) or "entreprise"
    else:
        first = _ascii_slug(first_name)
        last = _ascii_slug(last_name)
        base = ".".join(p for p in (first, last) if p) or "contact"

    qs = Member.objects.all()
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    candidate, n = base, 1
    while qs.filter(member_id=candidate).exists():
        n += 1
        candidate = f"{base}{n}"
    return candidate


def season_reference_year(on_date=None):
    from apps.dashboard.models import ClubSettings

    try:
        return ClubSettings.load().season_reference_year(on_date)
    except Exception:
        on_date = on_date or date.today()
        return on_date.year + 1 if on_date.month >= 9 else on_date.year


def age_on(birth_date, on_date=None):
    if not birth_date:
        return None
    on_date = on_date or date.today()
    years = on_date.year - birth_date.year
    if (on_date.month, on_date.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def age_category(birth_date, reference_year=None):
    """
    Catégorie calculée sur l'âge atteint dans l'année civile de fin de saison
    (usage courant en escrime : catégorie par année de naissance, revue chaque saison).
    """
    if not birth_date:
        return ""
    reference_year = reference_year or season_reference_year()
    age_in_season = reference_year - birth_date.year
    for limit, label in AGE_CATEGORIES:
        if age_in_season < limit:
            return label
    return "Vétéran"


def birth_year_range_for_category(label, reference_year=None):
    """Bornes (année_min, année_max) de naissance pour une catégorie donnée — sert aux filtres."""
    reference_year = reference_year or season_reference_year()
    lower = 0
    for limit, cat in AGE_CATEGORIES:
        if cat == label:
            # age in [lower, limit-1]  => birth year in [ref-limit+1, ref-lower]
            return reference_year - limit + 1, reference_year - lower
        lower = limit
    return None


def compute_contribution(base_amount, family_discount=False):
    if base_amount is None:
        return None
    amount = Decimal(base_amount)
    if family_discount:
        amount -= FAMILY_DISCOUNT_CHF
    return max(amount, Decimal("0.00"))


def format_avs(value):
    """Normalise un numéro AVS en 756.XXXX.XXXX.XX si 13 chiffres fournis."""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 13:
        return f"{digits[:3]}.{digits[3:7]}.{digits[7:11]}.{digits[11:]}"
    return (value or "").strip()


def avs_is_valid(value):
    """Contrôle du numéro AVS suisse (EAN-13) via python-stdnum."""
    from stdnum.ch import ssn

    digits = re.sub(r"\D", "", value or "")
    return ssn.is_valid(digits)
