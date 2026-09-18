"""
Filtres de la liste des contacts, basés sur n'importe quel champ (natif ou personnalisé).

Format d'un filtre dans l'URL : `f=<clé>:<opérateur>:<valeur>` (répétable).
Opérateurs : eq, ne, contains, empty, notempty, gt, lt, in.
Les champs natifs sont filtrés en base (ORM) ; les champs calculés et personnalisés en Python.
"""
from django.db.models import Q

from . import fields as F
from . import services

OPERATORS = [
    ("eq", "est égal à"),
    ("ne", "est différent de"),
    ("contains", "contient"),
    ("empty", "est vide"),
    ("notempty", "est renseigné"),
    ("gt", "est après / supérieur à"),
    ("lt", "est avant / inférieur à"),
]
OPERATOR_LABELS = dict(OPERATORS)

DB_FIELDS = {
    "title", "first_name", "last_name", "address", "postal_code", "city", "country", "sex", "birth_date",
    "nationality", "entry_date", "exit_date", "status", "member_id", "role", "avs_number", "laterality",
    "licence_number", "phone", "phone_parent1", "phone_parent2", "email", "email_alt", "email_parent1",
    "email_parent2", "notes", "kind", "profile",
}
FK_FIELDS = {"training_mode": "training_mode__name", "tariff_bracket": "tariff_bracket__name", "groups": "groups__name"}


def parse_filters(raw_list):
    parsed = []
    for raw in raw_list:
        parts = raw.split(":", 2)
        if len(parts) < 2:
            continue
        key, op = parts[0], parts[1]
        value = parts[2] if len(parts) > 2 else ""
        if op not in OPERATOR_LABELS:
            continue
        parsed.append({"key": key, "op": op, "value": value})
    return parsed


def describe(flt):
    label = F.field_label(flt["key"])
    op = OPERATOR_LABELS.get(flt["op"], flt["op"])
    if flt["op"] in ("empty", "notempty"):
        return f"{label} {op}"
    return f"{label} {op} « {flt['value']} »"


def apply_db_filters(qs, filters):
    """Applique en base ce qui peut l'être ; renvoie (qs, filtres restants à appliquer en Python)."""
    remaining = []
    for flt in filters:
        key, op, value = flt["key"], flt["op"], flt["value"]
        lookup = None
        if key in DB_FIELDS:
            lookup = key
        elif key in FK_FIELDS:
            lookup = FK_FIELDS[key]
        if lookup is None:
            remaining.append(flt)
            continue
        if op == "eq":
            qs = qs.filter(Q(**{f"{lookup}__iexact": value}))
        elif op == "ne":
            qs = qs.exclude(Q(**{f"{lookup}__iexact": value}))
        elif op == "contains":
            qs = qs.filter(Q(**{f"{lookup}__icontains": value}))
        elif op == "empty":
            qs = qs.filter(Q(**{f"{lookup}__isnull": True}) | Q(**{lookup: ""})) if key in DB_FIELDS else qs.filter(**{f"{key}__isnull": True})
        elif op == "notempty":
            qs = qs.exclude(Q(**{f"{lookup}__isnull": True}) | Q(**{lookup: ""})) if key in DB_FIELDS else qs.filter(**{f"{key}__isnull": False})
        elif op == "gt":
            qs = qs.filter(Q(**{f"{lookup}__gt": value}))
        elif op == "lt":
            qs = qs.filter(Q(**{f"{lookup}__lt": value}))
    return qs.distinct(), remaining


def apply_python_filters(members, filters):
    if not filters:
        return members
    out = []
    for m in members:
        ok = True
        for flt in filters:
            key, op, value = flt["key"], flt["op"], flt["value"]
            if key == "category":
                actual = m.category
            else:
                actual = F.display_value(m, key)
            actual_l = (actual or "").lower()
            value_l = value.lower()
            if op == "eq" and actual_l != value_l:
                ok = False
            elif op == "ne" and actual_l == value_l:
                ok = False
            elif op == "contains" and value_l not in actual_l:
                ok = False
            elif op == "empty" and actual_l:
                ok = False
            elif op == "notempty" and not actual_l:
                ok = False
            elif op == "gt" and not (actual_l > value_l):
                ok = False
            elif op == "lt" and not (actual_l < value_l):
                ok = False
            if not ok:
                break
        if ok:
            out.append(m)
    return out


def filterable_fields():
    """Champs proposés dans le constructeur de filtres, avec leurs options éventuelles."""
    out = []
    for d in F.all_field_definitions():
        bf = F.BUILTIN_BY_KEY.get(d.key)
        choices = []
        if bf and bf.choices:
            choices = [c[1] if bf.key in ("country", "nationality") else c[1] for c in bf.choices]
            if bf.key not in ("country", "nationality", "training_days"):
                choices = [c[1] for c in bf.choices]
        elif d.choices:
            choices = list(d.choices)
        if d.key == "category":
            choices = services.CATEGORY_LABELS
        out.append({"key": d.key, "label": d.label, "choices": choices, "type": d.field_type})
    return out
