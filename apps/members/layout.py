"""
Modèle des fiches membres : enregistrement de la mise en page propre à chaque profil
(Mineur / Majeur / Essai) depuis l'écran « Modèle des fiches ».

Pour chaque champ et chaque profil, le comité choisit : le libellé affiché, la section, la position
et la présence sur la fiche. Les règles suivantes protègent la cohérence de l'application :
  - Prénom, Nom et Statut ne peuvent pas être masqués (`LOCKED_FIELDS`) ;
  - le N° AVS reste toujours une donnée sensible ;
  - un libellé identique au libellé de base n'est pas mémorisé comme personnalisation.
"""
from . import fields as F
from .models import FieldDefinition, Profile


def is_shown(definition, profile):
    return definition.is_active and definition.applies_to(profile)


def save_layout(profile, post):
    """`post` : QueryDict du formulaire (ids dans l'ordre d'affichage, label_<id>, section_<id>, show_<id>, sens_<id>)."""
    if profile not in Profile.values:
        raise ValueError(f"Profil inconnu : {profile}")
    ids = [int(x) for x in post.getlist("ids") if x.isdigit()]
    definitions = {d.pk: d for d in FieldDefinition.objects.filter(pk__in=ids)}
    for index, pk in enumerate(ids):
        d = definitions.get(pk)
        if d is None:
            continue
        layout = dict(d.layout or {})
        entry = dict(layout.get(profile, {}))

        label = (post.get(f"label_{pk}") or "").strip()[:100]
        if label and label != d.label_for(profile):
            if label == d.label:
                entry.pop("label", None)
            else:
                entry["label"] = label

        section = post.get(f"section_{pk}")
        if section in F.SECTION_TITLES:
            if section == d.section_for(None):
                entry.pop("section", None)
            else:
                entry["section"] = section

        entry["order"] = (index + 1) * 10
        layout[profile] = entry
        d.layout = layout

        shown = post.get(f"show_{pk}") == "on" or d.key in F.LOCKED_FIELDS
        current = list(d.profiles or [])
        if shown and profile not in current:
            current.append(profile)
        if not shown and profile in current:
            current.remove(profile)
        d.profiles = current

        d.is_sensitive = post.get(f"sens_{pk}") == "on" or d.key == "avs_number"
        d.save()


def reset_layout(profile):
    """Rétablit le modèle d'origine d'un profil (champs natifs, ordre, sections, libellés)."""
    if profile not in Profile.values:
        raise ValueError(f"Profil inconnu : {profile}")
    for d in FieldDefinition.objects.all():
        layout = dict(d.layout or {})
        layout.pop(profile, None)
        bf = F.BUILTIN_BY_KEY.get(d.key)
        if bf:
            if bf.labels_by_profile.get(profile):
                layout[profile] = {"label": bf.labels_by_profile[profile]}
            current = list(d.profiles or [])
            if profile in bf.profiles and profile not in current:
                current.append(profile)
            if profile not in bf.profiles and profile in current:
                current.remove(profile)
            d.profiles = current
        d.layout = layout
        d.save()
