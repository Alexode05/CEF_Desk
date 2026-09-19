import logging

from django.contrib import messages
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Count, Max
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.billing.models import EmailLog
from apps.dashboard.models import ClubSettings
from apps.documents.services import store_generated_file
from apps.members.models import Profile

from .forms import AddFieldForm, FormDefinitionForm, FormFieldEditForm
from .models import FormDefinition, FormField, FormSubmission
from .public_forms import PublicForm

logger = logging.getLogger(__name__)


# --- Gestion (comité) ----------------------------------------------------------


def form_list(request):
    forms_qs = FormDefinition.objects.annotate(n_fields=Count("fields", distinct=True), n_sub=Count("submissions", distinct=True))
    return render(request, "formbuilder/list.html", {"forms": forms_qs, "pending": FormSubmission.objects.filter(member__status="EN_ATTENTE").count()})


def form_create(request):
    form = FormDefinitionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        fd = form.save(commit=False)
        fd.created_by = request.user
        fd.save()
        form.save_m2m()
        _seed_default_fields(fd)
        _archive_definition(fd, request.user)
        messages.success(request, "Formulaire créé avec les champs de base. Ajustez la liste des champs ci-dessous.")
        return redirect("formbuilder:edit", pk=fd.pk)
    return render(request, "formbuilder/create.html", {"form": form})


def _seed_default_fields(fd):
    """Pré-remplit le formulaire avec les champs de la fiche correspondant au profil choisi."""
    from apps.members import fields as F
    from apps.members.models import FieldDefinition

    order = 0
    if fd.profile != Profile.ESSAI:
        FormField.objects.create(form=fd, order=order, kind=FormField.Kind.PROFILE, required=True)
        order += 10
    profile_field = fd.fields.filter(kind=FormField.Kind.PROFILE).first()
    for d in sorted(FieldDefinition.objects.filter(is_active=True, is_builtin=True), key=lambda x: x.order_for(fd.profile)):
        if d.key in F.NOT_IN_PUBLIC_FORMS:
            continue
        if fd.profile == Profile.ESSAI:
            if not d.applies_to(Profile.ESSAI):
                continue
        elif not (d.applies_to(Profile.MINEUR) or d.applies_to(Profile.MAJEUR)):
            continue
        ff = FormField(form=fd, order=order, kind=FormField.Kind.FIELD, field_definition=d, required=d.key in ("first_name", "last_name", "birth_date", "address", "postal_code", "city"))
        # Champs propres aux mineurs / majeurs : conditionnés au type d'inscription.
        if profile_field and d.profiles == [Profile.MINEUR]:
            ff.condition_field, ff.condition_operator, ff.condition_value = profile_field, "eq", Profile.MINEUR
            ff.required = d.key in ("phone_parent1", "email_parent1")
        elif profile_field and d.profiles == [Profile.MAJEUR]:
            ff.condition_field, ff.condition_operator, ff.condition_value = profile_field, "eq", Profile.MAJEUR
        ff.save()
        order += 10


def _archive_definition(fd, user=None):
    try:
        store_generated_file("Club/Formulaires", f"Formulaire_{fd.slug}.json", fd.export_definition().encode("utf-8"), "application/json", user=user)
    except Exception:  # noqa: BLE001
        logger.exception("Archivage du modèle de formulaire impossible")


def form_edit(request, pk):
    fd = get_object_or_404(FormDefinition, pk=pk)
    settings_form = FormDefinitionForm(request.POST or None, instance=fd, prefix="s")
    add_form = AddFieldForm(request.POST or None, form_definition=fd, prefix="a")
    if request.method == "POST":
        if "save_settings" in request.POST and settings_form.is_valid():
            settings_form.save()
            _archive_definition(fd, request.user)
            messages.success(request, "Paramètres du formulaire enregistrés.")
            return redirect("formbuilder:edit", pk=pk)
        if "add_field" in request.POST and add_form.is_valid():
            last = fd.fields.aggregate(m=Max("order"))["m"] or 0
            FormField.objects.create(
                form=fd, order=last + 10, kind=add_form.cleaned_data["kind"],
                field_definition=add_form.cleaned_data.get("field_definition") if add_form.cleaned_data["kind"] == "FIELD" else None,
                text=add_form.cleaned_data.get("text", ""), required=add_form.cleaned_data.get("required", False),
            )
            _archive_definition(fd, request.user)
            messages.success(request, "Élément ajouté en fin de formulaire.")
            return redirect("formbuilder:edit", pk=pk)
    add_form = AddFieldForm(form_definition=fd, prefix="a") if request.method == "POST" and "add_field" not in request.POST else add_form
    return render(
        request,
        "formbuilder/edit.html",
        {"fd": fd, "settings_form": settings_form, "add_form": add_form, "fields": fd.fields.select_related("field_definition", "condition_field"), "public_url": request.build_absolute_uri(fd.get_public_url())},
    )


def field_edit(request, pk):
    ff = get_object_or_404(FormField.objects.select_related("form"), pk=pk)
    form = FormFieldEditForm(request.POST or None, instance=ff)
    if request.method == "POST" and form.is_valid():
        form.save()
        _archive_definition(ff.form, request.user)
        messages.success(request, "Élément modifié.")
        return redirect("formbuilder:edit", pk=ff.form_id)
    return render(request, "formbuilder/field_edit.html", {"form": form, "ff": ff})


@require_POST
def field_move(request, pk, direction):
    ff = get_object_or_404(FormField, pk=pk)
    siblings = list(ff.form.fields.all())
    idx = siblings.index(ff)
    swap = idx - 1 if direction == "up" else idx + 1
    if 0 <= swap < len(siblings):
        other = siblings[swap]
        ff.order, other.order = other.order, ff.order
        if ff.order == other.order:
            other.order += 1 if direction == "up" else -1
        ff.save(update_fields=["order"])
        other.save(update_fields=["order"])
    return redirect("formbuilder:edit", pk=ff.form_id)


@require_POST
def field_delete(request, pk):
    ff = get_object_or_404(FormField, pk=pk)
    form_id = ff.form_id
    ff.delete()
    _archive_definition(FormDefinition.objects.get(pk=form_id), request.user)
    messages.success(request, "Élément retiré du formulaire.")
    return redirect("formbuilder:edit", pk=form_id)


@require_POST
def form_delete(request, pk):
    fd = get_object_or_404(FormDefinition, pk=pk)
    if request.POST.get("confirm") != fd.slug:
        messages.error(request, "Confirmation incorrecte : recopiez l'adresse publique du formulaire.")
        return redirect("formbuilder:edit", pk=pk)
    fd.delete()
    messages.success(request, "Formulaire supprimé (les soumissions déjà reçues sont conservées).")
    return redirect("formbuilder:list")


def submission_list(request):
    subs = FormSubmission.objects.select_related("member", "form")
    form_id = request.GET.get("form")
    if form_id:
        subs = subs.filter(form_id=form_id)
    return render(request, "formbuilder/submissions.html", {"submissions": subs[:300], "forms": FormDefinition.objects.all(), "form_id": form_id})


def submission_detail(request, pk):
    sub = get_object_or_404(FormSubmission.objects.select_related("member"), pk=pk)
    return render(request, "formbuilder/submission_detail.html", {"sub": sub})


# --- Public -------------------------------------------------------------------------


def public_form(request, slug):
    fd = get_object_or_404(FormDefinition, slug=slug)
    if not fd.is_active:
        return render(request, "formbuilder/public_closed.html", {"fd": fd}, status=404)
    form = PublicForm(fd, request.POST or None)
    if request.method == "POST" and form.is_valid():
        submission = _process_submission(fd, form)
        return render(request, "formbuilder/public_success.html", {"fd": fd, "submission": submission})
    rules = [
        {"target": ff.input_name, "source": ff.condition_field.input_name, "op": ff.condition_operator, "value": ff.condition_value}
        for ff in form.form_fields
        if ff.condition_field_id and (ff.is_input or True)
    ]
    return render(request, "formbuilder/public_form.html", {"fd": fd, "form": form, "rules": rules, "club": ClubSettings.load()})


@transaction.atomic
def _process_submission(fd, form):
    member = form.build_member()
    member.save()
    for g in fd.default_groups.all():
        member.groups.add(g)
    for g in getattr(form, "selected_groups", []):  # groupes choisis par la personne
        member.groups.add(g)
    answers = form.answers()
    submission = FormSubmission.objects.create(form=fd, form_name=fd.name, data=answers, profile=member.profile, member=member)
    _notify_secretariat(fd, submission, answers)
    return submission


def _notify_secretariat(fd, submission, answers):
    club = ClubSettings.load()
    to = fd.notify_email or club.secretariat_email
    if not to:
        return
    lines = [f"Nouvelle soumission du formulaire « {fd.name} » le {submission.submitted_at:%d.%m.%Y à %H:%M}.", ""]
    lines += [f"{a['label']} : {a['value'] or '—'}" for a in answers]
    lines += ["", f"Une fiche « en attente de validation » a été créée (profil {submission.get_profile_display()}).", "Connectez-vous à CEF Desk pour la vérifier et la valider."]
    subject = f"[CEF Desk] Nouvelle inscription — {submission.summary_name} ({fd.name})"
    log = EmailLog(kind="notification", to=to, subject=subject, member=submission.member)
    try:
        EmailMessage(subject=subject, body="\n".join(lines), to=[to]).send(fail_silently=False)
        submission.notified = True
    except Exception as exc:  # noqa: BLE001
        logger.exception("Notification secrétariat impossible")
        submission.notify_error = str(exc)
        log.ok, log.error = False, str(exc)
    submission.save(update_fields=["notified", "notify_error"])
    log.save()
