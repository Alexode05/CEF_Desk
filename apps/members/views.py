import csv
import io

from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import fields as F
from . import filters as FL
from .forms import ContactGroupForm, FieldDefinitionForm, ImportForm, MassEditForm, MemberForm, ValidateMemberForm
from .models import (
    ContactGroup,
    ContactKind,
    FieldDefinition,
    Member,
    MemberStatus,
    Profile,
    SavedView,
    UserListPreference,
)

CATEGORIES = [
    ("tous", "Tous les contacts"),
    ("personnes", "Personnes"),
    ("membres", "Membres"),
    ("non-membres", "Non-membres"),
    ("entreprises", "Entreprises"),
]


def _category_qs(cat):
    qs = Member.objects.all()
    return {
        "personnes": qs.persons(),
        "membres": qs.members(),
        "non-membres": qs.non_members(),
        "entreprises": qs.companies(),
    }.get(cat, qs)


def _user_columns(user):
    pref = UserListPreference.objects.filter(user=user).first()
    cols = pref.columns if pref and pref.columns else list(F.DEFAULT_LIST_COLUMNS)
    valid = {d.key for d in F.all_field_definitions()}
    return [c for c in cols if c in valid] or list(F.DEFAULT_LIST_COLUMNS)


def member_list(request):
    cat = request.GET.get("cat", "tous")
    group_id = request.GET.get("group")
    status = request.GET.get("status", "")
    query = request.GET.get("q", "").strip()
    view_id = request.GET.get("view")
    raw_filters = request.GET.getlist("f")

    saved_view = None
    if view_id:
        saved_view = SavedView.objects.filter(pk=view_id).first()
        if saved_view:
            raw_filters = raw_filters or [f"{x['key']}:{x['op']}:{x['value']}" for x in saved_view.filters]
            cat = saved_view.category or cat
            group_id = group_id or (str(saved_view.group_id) if saved_view.group_id else None)

    qs = _category_qs(cat).select_related("training_mode", "tariff_bracket").prefetch_related("groups")
    group = None
    if group_id:
        group = ContactGroup.objects.filter(pk=group_id).first()
        if group:
            qs = qs.filter(groups=group)
    if status:
        qs = qs.filter(status=status)
    if query:
        qs = qs.filter(
            Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(member_id__icontains=query)
            | Q(email__icontains=query) | Q(city__icontains=query) | Q(company_name__icontains=query)
            | Q(licence_number__icontains=query)
        )

    filters = FL.parse_filters(raw_filters)
    qs, py_filters = FL.apply_db_filters(qs, filters)
    members = FL.apply_python_filters(list(qs), py_filters)

    columns = (saved_view.columns if saved_view and saved_view.columns else None) or _user_columns(request.user)
    defs = {d.key: d for d in F.all_field_definitions()}
    column_headers = [(k, defs[k].label if k in defs else k) for k in columns]
    rows = []
    for m in members:
        cells = []
        for k in columns:
            d = defs.get(k)
            if d and d.is_sensitive:
                cells.append(m.avs_masked if k == "avs_number" else "•••")
            else:
                cells.append(F.display_value(m, k))
        rows.append((m, cells))

    group_counts = ContactGroup.objects.annotate(n=Count("members"))
    cat_counts = {c: _category_qs(c).count() for c, _ in CATEGORIES}

    return render(
        request,
        "members/list.html",
        {
            "categories": CATEGORIES,
            "cat": cat,
            "cat_counts": cat_counts,
            "groups": group_counts,
            "group": group,
            "status": status,
            "status_choices": MemberStatus.choices,
            "query": query,
            "rows": rows,
            "count": len(rows),
            "columns": columns,
            "column_headers": column_headers,
            "all_fields": [d for d in defs.values()],
            "filters": filters,
            "filter_descriptions": [(f"{x['key']}:{x['op']}:{x['value']}", FL.describe(x)) for x in filters],
            "filterable_fields": FL.filterable_fields(),
            "operators": FL.OPERATORS,
            "saved_views": SavedView.objects.all(),
            "saved_view": saved_view,
            "mass_form": MassEditForm(),
            "profiles": Profile.choices,
        },
    )


@require_POST
def save_columns(request):
    cols = [c for c in request.POST.getlist("columns") if c]
    pref, _ = UserListPreference.objects.get_or_create(user=request.user)
    pref.columns = cols or list(F.DEFAULT_LIST_COLUMNS)
    pref.save()
    return redirect(request.POST.get("next") or "members:list")


@require_POST
def save_view(request):
    name = request.POST.get("name", "").strip()
    if not name:
        return HttpResponseBadRequest("Nom requis")
    filters = FL.parse_filters(request.POST.getlist("f"))
    SavedView.objects.create(
        name=name,
        columns=_user_columns(request.user),
        filters=filters,
        category=request.POST.get("cat", ""),
        group_id=request.POST.get("group") or None,
        created_by=request.user,
    )
    messages.success(request, f"Vue « {name} » enregistrée.")
    return redirect("members:list")


@require_POST
def delete_view(request, pk):
    SavedView.objects.filter(pk=pk).delete()
    return redirect("members:list")


def member_detail(request, pk):
    member = get_object_or_404(Member.objects.select_related("training_mode", "tariff_bracket"), pk=pk)
    defs = F.all_field_definitions(member.profile)
    sections = {}
    for d in defs:
        bf = F.BUILTIN_BY_KEY.get(d.key)
        section = bf.section if bf else "custom"
        if d.key in ("member_id", "status"):
            continue  # affichés dans l'en-tête
        label = bf.label_for(member.profile) if bf else d.label
        value = F.display_value(member, d.key)
        sections.setdefault(section, []).append({"key": d.key, "label": label, "value": value, "sensitive": d.is_sensitive})
    ordered = [(F.SECTION_TITLES[s], sections[s]) for s in ["general", "membership", "contact", "fencing", "training", "custom", "meta"] if s in sections]
    finance = sections.get("finance", [])
    validate_form = None
    if member.status == MemberStatus.EN_ATTENTE and member.profile != Profile.ESSAI:
        validate_form = ValidateMemberForm(
            initial={"training_mode": member.training_mode, "tariff_bracket": member.tariff_bracket, "family_discount": member.family_discount}
        )
    return render(
        request,
        "members/detail.html",
        {"member": member, "sections": ordered, "finance": finance, "invoices": member.invoices.all()[:20], "validate_form": validate_form},
    )


def member_create(request):
    profile = request.GET.get("profile") or request.POST.get("profile")
    if profile not in Profile.values:
        return render(request, "members/choose_profile.html", {"profiles": Profile.choices})
    form = MemberForm(request.POST or None, profile=profile)
    if request.method == "POST" and form.is_valid():
        member = form.save(commit=False)
        member.created_by = request.user
        member.save()
        form.save_m2m()
        messages.success(request, f"Fiche de {member.display_name} créée (ID : {member.member_id}).")
        return redirect(member)
    return render(request, "members/form.html", {"form": form, "profile": profile, "profile_label": Profile(profile).label})


def member_edit(request, pk):
    member = get_object_or_404(Member, pk=pk)
    form = MemberForm(request.POST or None, instance=member, profile=member.profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Fiche enregistrée.")
        return redirect(member)
    return render(
        request,
        "members/form.html",
        {"form": form, "member": member, "profile": member.profile, "profile_label": member.get_profile_display()},
    )


def member_delete(request, pk):
    member = get_object_or_404(Member, pk=pk)
    if request.method == "POST":
        if request.POST.get("confirm") != member.member_id:
            messages.error(request, "Confirmation incorrecte : recopiez l'ID de la fiche pour la supprimer.")
            return redirect("members:delete", pk=pk)
        if member.invoices.exists():
            messages.error(request, "Impossible de supprimer une fiche qui possède des factures. Passez-la en « Inactif » à la place.")
            return redirect(member)
        name = member.display_name
        member.delete()
        messages.success(request, f"Fiche de {name} supprimée définitivement.")
        return redirect("members:list")
    return render(request, "members/delete.html", {"member": member})


@require_POST
def member_validate(request, pk):
    """Validation d'une inscription : En attente → Actif (ou Essai pour un profil Essai)."""
    member = get_object_or_404(Member, pk=pk)
    if member.status != MemberStatus.EN_ATTENTE:
        messages.info(request, "Cette fiche n'est pas en attente de validation.")
        return redirect(member)
    if member.profile == Profile.ESSAI:
        member.status = MemberStatus.ESSAI
    else:
        form = ValidateMemberForm(request.POST)
        if not form.is_valid():
            problems = "; ".join(f"{form.fields[k].label} : {' '.join(v)}" for k, v in form.errors.items())
            messages.error(request, f"Validation impossible — {problems}")
            return redirect(member)
        cleaned = form.cleaned_data
        member.tariff_bracket = cleaned["tariff_bracket"]
        member.family_discount = cleaned["family_discount"]
        if cleaned.get("training_mode"):
            member.training_mode = cleaned["training_mode"]
        member.entry_date = cleaned.get("entry_date") or member.entry_date or timezone.localdate()
        member.status = MemberStatus.ACTIF
    member.save()
    messages.success(request, f"Inscription de {member.display_name} validée — statut « {member.get_status_display()} ».")
    return redirect(member)


@require_POST
def mass_edit(request):
    form = MassEditForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Modification de masse invalide : " + "; ".join(f"{k} : {' '.join(v)}" for k, v in form.errors.items()))
        return redirect(request.POST.get("next") or "members:list")
    ids = form.member_ids()
    qs = Member.objects.filter(pk__in=ids)
    action = form.cleaned_data["action"]
    n = qs.count()
    if action == "status":
        for m in qs:
            m.status = form.cleaned_data["status"]
            m.save()
    elif action == "add_group":
        form.cleaned_data["group"].members.add(*qs)
    elif action == "remove_group":
        form.cleaned_data["group"].members.remove(*qs)
    elif action == "training_mode":
        qs.update(training_mode=form.cleaned_data["training_mode"])
    elif action == "tariff_bracket":
        qs.update(tariff_bracket=form.cleaned_data["tariff_bracket"])
    elif action == "exit_date":
        qs.update(exit_date=form.cleaned_data["exit_date"])
    messages.success(request, f"Modification appliquée à {n} contact(s).")
    return redirect(request.POST.get("next") or "members:list")


# --- Groupes ---------------------------------------------------------------


def group_manage(request):
    form = ContactGroupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Groupe créé.")
        return redirect("members:groups")
    groups = ContactGroup.objects.annotate(n=Count("members"))
    return render(request, "members/groups.html", {"form": form, "groups": groups})


def group_edit(request, pk):
    group = get_object_or_404(ContactGroup, pk=pk)
    form = ContactGroupForm(request.POST or None, instance=group)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Groupe modifié.")
        return redirect("members:groups")
    return render(request, "members/group_form.html", {"form": form, "group": group})


@require_POST
def group_delete(request, pk):
    group = get_object_or_404(ContactGroup, pk=pk)
    group.delete()
    messages.success(request, f"Groupe « {group.name} » supprimé (les contacts sont conservés).")
    return redirect("members:groups")


# --- Champs personnalisés --------------------------------------------------


def field_manage(request):
    form = FieldDefinitionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Champ ajouté. Il apparaît désormais sur les fiches concernées, dans le sélecteur de colonnes, les filtres, les exports et l'éditeur de formulaires.")
        return redirect("members:fields")
    return render(
        request,
        "members/fields.html",
        {
            "form": form,
            "builtin": FieldDefinition.objects.filter(is_builtin=True),
            "custom": FieldDefinition.objects.filter(is_builtin=False),
        },
    )


def field_edit(request, pk):
    fd = get_object_or_404(FieldDefinition, pk=pk, is_builtin=False)
    form = FieldDefinitionForm(request.POST or None, instance=fd)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Champ modifié.")
        return redirect("members:fields")
    return render(request, "members/field_form.html", {"form": form, "field": fd})


@require_POST
def field_delete(request, pk):
    fd = get_object_or_404(FieldDefinition, pk=pk, is_builtin=False)
    fd.delete()
    messages.success(request, f"Champ « {fd.label} » supprimé. Les valeurs déjà saisies restent stockées mais ne sont plus affichées.")
    return redirect("members:fields")


@require_POST
def field_toggle_sensitive(request, pk):
    fd = get_object_or_404(FieldDefinition, pk=pk)
    if fd.key == "avs_number":
        messages.error(request, "Le N° AVS est toujours traité comme sensible.")
    else:
        fd.is_sensitive = not fd.is_sensitive
        fd.save(update_fields=["is_sensitive"])
    return redirect("members:fields")


# --- Import CSV ------------------------------------------------------------


def member_import(request):
    form = ImportForm(request.POST or None, request.FILES or None)
    report = None
    if request.method == "POST" and form.is_valid():
        raw = form.cleaned_data["file"].read()
        text = None
        for enc in ("utf-8-sig", "utf-8", "cp1252", "mac_roman"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            messages.error(request, "Encodage du fichier non reconnu.")
            return redirect("members:import")
        sample = text[:2000]
        delimiter = ";" if sample.count(";") >= sample.count(",") else ","
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        profile = form.cleaned_data["profile"]
        status = form.cleaned_data["status"]
        label_to_key = {}
        for d in F.all_field_definitions(profile):
            label_to_key[d.label.lower()] = d.key
            bf = F.BUILTIN_BY_KEY.get(d.key)
            if bf:
                for lbl in bf.labels_by_profile.values():
                    label_to_key[lbl.lower()] = d.key
        created, skipped, errors = 0, 0, []
        for i, row in enumerate(reader, start=2):
            data = {}
            for header, value in row.items():
                if header is None:
                    continue
                key = label_to_key.get(header.strip().lower())
                if key and value is not None:
                    data[key] = value.strip()
            if not data.get("first_name") and not data.get("last_name"):
                skipped += 1
                continue
            try:
                member = _member_from_import(data, profile, status)
                member.created_by = request.user
                member.save()
                if data.get("groups"):
                    for gname in [g.strip() for g in data["groups"].split(",") if g.strip()]:
                        grp, _ = ContactGroup.objects.get_or_create(name=gname)
                        member.groups.add(grp)
                created += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Ligne {i} : {exc}")
        report = {"created": created, "skipped": skipped, "errors": errors}
    return render(request, "members/import.html", {"form": form, "report": report})


def _member_from_import(data, profile, status):
    from datetime import datetime

    from .models import COUNTRY_LABELS, NATIONALITY_LABELS, WEEKDAY_LABELS

    def parse_date(v):
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(v, fmt).date()
            except ValueError:
                continue
        return None

    def reverse_lookup(mapping, v):
        v_l = v.lower()
        for code, label in mapping.items():
            if v_l in (code.lower(), label.lower()):
                return code
        return ""

    m = Member(profile=profile, status=status)
    custom = {}
    for key, value in data.items():
        bf = F.BUILTIN_BY_KEY.get(key)
        if bf is None:
            custom[key] = value
            continue
        if bf.computed or key == "groups":
            continue
        if key in ("birth_date", "entry_date", "exit_date"):
            setattr(m, key, parse_date(value))
        elif key == "country":
            m.country = reverse_lookup(COUNTRY_LABELS, value) or "CH"
        elif key == "nationality":
            m.nationality = reverse_lookup(NATIONALITY_LABELS, value)
        elif key in ("title", "sex", "status", "laterality"):
            field = Member._meta.get_field(key)
            m_choices = {c[0].lower(): c[0] for c in field.choices} | {c[1].lower(): c[0] for c in field.choices}
            setattr(m, key, m_choices.get(value.lower(), "") if value else "")
        elif key == "training_days":
            m.training_days = [reverse_lookup(WEEKDAY_LABELS, d.strip()) for d in value.split(",") if d.strip()]
        elif key == "training_mode":
            from .models import TrainingMode

            m.training_mode = TrainingMode.objects.filter(name__iexact=value).first()
        elif key == "tariff_bracket":
            from .models import TariffBracket

            m.tariff_bracket = TariffBracket.objects.filter(name__iexact=value).first()
        elif key == "family_discount":
            m.family_discount = value.lower() in ("oui", "yes", "1", "true", "x")
        elif key == "avs_number":
            from . import services

            m.avs_number = services.format_avs(value)
        else:
            setattr(m, key, value)
    if profile == Profile.ESSAI:
        m.status = MemberStatus.ESSAI if status not in (MemberStatus.EN_ATTENTE, MemberStatus.INACTIF) else status
    m.custom_data = custom
    return m
