"""
Registre des champs natifs de la fiche membre et de leur applicabilité par profil.

Ce registre alimente la table `FieldDefinition` (via `sync_builtin_fields`), le formulaire
de fiche (`forms.py`), le sélecteur de colonnes, les filtres, l'export et l'éditeur de formulaires.
Les libellés dépendant du profil (« Email élève » vs « Email ») sont gérés ici.
"""
from dataclasses import dataclass, field

from .models import (
    COUNTRIES,
    NATIONALITIES,
    WEEKDAYS,
    Laterality,
    MemberStatus,
    Profile,
    Sex,
    Title,
)

ALL = [Profile.MINEUR, Profile.MAJEUR, Profile.ESSAI]
MIN_MAJ = [Profile.MINEUR, Profile.MAJEUR]


@dataclass
class BuiltinField:
    key: str
    label: str
    field_type: str
    profiles: list
    section: str = "general"  # general | contact | fencing | training | finance | meta
    choices: list = field(default_factory=list)
    labels_by_profile: dict = field(default_factory=dict)
    sensitive: bool = False
    computed: bool = False  # lecture seule (calculé)
    sort_order: int = 100
    help_text: str = ""

    def label_for(self, profile):
        return self.labels_by_profile.get(profile, self.label)


def _choices(tc):
    return [(c.value, c.label) for c in tc]


BUILTIN_FIELDS = [
    # --- Général ---
    BuiltinField("title", "Titre", "SELECT", ALL, "general", _choices(Title), sort_order=10),
    BuiltinField("first_name", "Prénom", "TEXT", ALL, "general", sort_order=20),
    BuiltinField("last_name", "Nom", "TEXT", ALL, "general", sort_order=30),
    BuiltinField("address", "Adresse", "TEXT", ALL, "general", sort_order=40),
    BuiltinField("postal_code", "Code postal", "TEXT", ALL, "general", sort_order=50),
    BuiltinField("city", "Ville", "TEXT", ALL, "general", sort_order=60),
    BuiltinField("country", "Pays", "SELECT", ALL, "general", list(COUNTRIES), sort_order=70),
    BuiltinField("sex", "Sexe", "SELECT", ALL, "general", _choices(Sex), sort_order=80),
    BuiltinField("birth_date", "Date de naissance", "DATE", ALL, "general", sort_order=90),
    BuiltinField("category", "Catégorie", "TEXT", MIN_MAJ, "general", computed=True, sort_order=95),
    BuiltinField("nationality", "Nationalité", "SELECT", ALL, "general", list(NATIONALITIES), sort_order=100),
    # --- Adhésion ---
    BuiltinField("entry_date", "Entrée", "DATE", MIN_MAJ, "membership", sort_order=110),
    BuiltinField("exit_date", "Sortie", "DATE", MIN_MAJ, "membership", sort_order=120),
    BuiltinField("status", "Statut", "SELECT", ALL, "membership", _choices(MemberStatus), sort_order=130),
    BuiltinField("member_id", "ID", "TEXT", ALL, "membership", computed=True, sort_order=140),
    BuiltinField("role", "Rôle", "TEXT", MIN_MAJ, "membership", sort_order=150),
    BuiltinField("groups", "Groupe", "MULTISELECT", ALL, "membership", sort_order=160),
    # --- Escrime ---
    BuiltinField("avs_number", "N° AVS", "TEXT", MIN_MAJ, "fencing", sensitive=True, sort_order=200, help_text="Format 756.XXXX.XXXX.XX"),
    BuiltinField("laterality", "Latéralité", "SELECT", MIN_MAJ, "fencing", _choices(Laterality), sort_order=210),
    BuiltinField("licence_number", "N° de licence", "TEXT", MIN_MAJ, "fencing", sort_order=220),
    # --- Contact ---
    BuiltinField("phone", "Téléphone élève", "PHONE", ALL, "contact", sort_order=300),
    BuiltinField("phone_parent1", "Téléphone parent 1", "PHONE", [Profile.MINEUR], "contact", sort_order=310),
    BuiltinField("phone_parent2", "Téléphone parent 2", "PHONE", [Profile.MINEUR], "contact", sort_order=320),
    BuiltinField(
        "email", "Email", "EMAIL", ALL, "contact",
        labels_by_profile={Profile.MINEUR: "Email élève"}, sort_order=330,
    ),
    BuiltinField("email_alt", "Email alternative", "EMAIL", [Profile.MAJEUR], "contact", sort_order=340),
    BuiltinField("email_parent1", "Email parent 1", "EMAIL", [Profile.MINEUR], "contact", sort_order=350),
    BuiltinField("email_parent2", "Email parent 2", "EMAIL", [Profile.MINEUR], "contact", sort_order=360),
    # --- Entraînement ---
    BuiltinField("training_mode", "Modalité d'entraînement", "SELECT", MIN_MAJ, "training", sort_order=400),
    BuiltinField("training_days", "Jours d'entraînement", "WEEKDAYS", MIN_MAJ, "training", list(WEEKDAYS), sort_order=410),
    # --- Finance (complété par le comité, jamais dans le formulaire public) ---
    BuiltinField("tariff_bracket", "Tranche tarifaire", "SELECT", MIN_MAJ, "finance", sort_order=500),
    BuiltinField("family_discount", "Réduction famille", "BOOLEAN", MIN_MAJ, "finance", sort_order=510),
    BuiltinField("computed_amount", "Cotisation calculée", "TEXT", MIN_MAJ, "finance", computed=True, sort_order=520),
    BuiltinField("invoice_status_label", "Dernière facture", "TEXT", MIN_MAJ, "finance", computed=True, sort_order=530),
    # --- Divers ---
    BuiltinField("notes", "Remarques internes", "TEXTAREA", ALL, "meta", sort_order=900),
    BuiltinField("created_at", "Créé le", "DATE", ALL, "meta", computed=True, sort_order=910),
]

BUILTIN_BY_KEY = {f.key: f for f in BUILTIN_FIELDS}

# Champs qui ne doivent JAMAIS être proposés dans un formulaire public (section 5 : tranche
# tarifaire, statut étudiant, réduction famille saisis par le comité ; + champs internes).
NOT_IN_PUBLIC_FORMS = {
    "status", "member_id", "role", "entry_date", "exit_date", "tariff_bracket", "family_discount",
    "computed_amount", "invoice_status_label", "notes", "created_at", "category", "groups",
}

# Colonnes par défaut de la liste (décision section 4) — le N° AVS n'y figure jamais par défaut.
DEFAULT_LIST_COLUMNS = ["last_name", "first_name", "address"]

SECTION_TITLES = {
    "general": "Identité et adresse",
    "membership": "Adhésion",
    "fencing": "Escrime",
    "contact": "Contact",
    "training": "Entraînement",
    "finance": "Finance",
    "meta": "Divers",
    "custom": "Champs personnalisés",
}


def sync_builtin_fields():
    """Crée/met à jour les `FieldDefinition` natifs à partir de ce registre (idempotent)."""
    from .models import FieldDefinition

    for f in BUILTIN_FIELDS:
        FieldDefinition.objects.update_or_create(
            key=f.key,
            defaults={
                "label": f.label,
                "field_type": f.field_type,
                "profiles": list(f.profiles),
                "is_builtin": True,
                "is_sensitive": f.sensitive,
                "sort_order": f.sort_order,
                "help_text": f.help_text,
            },
        )


def all_field_definitions(profile=None, include_inactive=False):
    """Liste ordonnée des définitions (natives + personnalisées), filtrée par profil si demandé."""
    from .models import FieldDefinition

    qs = FieldDefinition.objects.all()
    if not include_inactive:
        qs = qs.filter(is_active=True)
    defs = list(qs)
    if profile:
        defs = [d for d in defs if d.applies_to(profile)]
    return defs


def field_label(key, profile=None):
    if key in BUILTIN_BY_KEY:
        return BUILTIN_BY_KEY[key].label_for(profile) if profile else BUILTIN_BY_KEY[key].label
    from .models import FieldDefinition

    d = FieldDefinition.objects.filter(key=key).first()
    return d.label if d else key


def display_value(member, key):
    """Valeur lisible d'un champ (natif ou personnalisé) pour la liste, la fiche, l'export."""
    from .models import COUNTRY_LABELS, NATIONALITY_LABELS, WEEKDAY_LABELS, FieldDefinition

    if key in BUILTIN_BY_KEY:
        if key == "groups":
            return ", ".join(g.name for g in member.groups.all())
        if key == "training_days":
            return ", ".join(WEEKDAY_LABELS.get(d, d) for d in member.training_days or [])
        if key == "country":
            return COUNTRY_LABELS.get(member.country, member.country)
        if key == "nationality":
            return NATIONALITY_LABELS.get(member.nationality, member.nationality)
        if key in ("training_mode", "tariff_bracket"):
            obj = getattr(member, key)
            return str(obj) if obj else ""
        if key == "family_discount":
            return "Oui" if member.family_discount else "Non"
        if key == "computed_amount":
            amt = member.computed_amount
            return f"CHF {amt:.2f}" if amt is not None else ""
        if key == "created_at":
            return member.created_at.strftime("%d.%m.%Y") if member.created_at else ""
        if key in ("birth_date", "entry_date", "exit_date"):
            v = getattr(member, key)
            return v.strftime("%d.%m.%Y") if v else ""
        if key in ("title", "sex", "status", "laterality"):
            getter = getattr(member, f"get_{key}_display", None)
            return getter() if getter and getattr(member, key) else ""
        value = getattr(member, key, "")
        return "" if value is None else str(value)

    # Champ personnalisé
    value = (member.custom_data or {}).get(key)
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    d = FieldDefinition.objects.filter(key=key).first()
    if d and d.field_type == "WEEKDAYS":
        return ", ".join(WEEKDAY_LABELS.get(v, v) for v in (value if isinstance(value, list) else [value]))
    return str(value)
