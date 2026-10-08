from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.emails import dev_email_preview_enabled
from apps.formbuilder.models import FormDefinition
from apps.dashboard.models import ClubSettings

from . import services
from .forms import LaunchForm, RenewalBillingForm, RenewalForm
from .models import RenewalRequest, SeasonRollover

Status = RenewalRequest.Status


# --- Comité ---------------------------------------------------------------------------------------


def launch(request):
    """Page « Passage à la saison suivante » : choix de la saison, texte de l'email, destinataires."""
    choices = services.season_choices()
    season = request.POST.get("target_season") or request.GET.get("saison") or choices[0][0]
    if season not in dict(choices):
        season = choices[0][0]
    existing = SeasonRollover.objects.filter(target_season=season).first()
    initial = {"target_season": season}
    if existing:
        initial.update(subject=existing.subject, body=existing.body)
    form = LaunchForm(request.POST or None, initial=initial, season_choices=choices)

    members = list(services.eligible_members())
    invited = set(existing.requests.exclude(status=Status.FAILED).values_list("member_id", flat=True)) if existing else set()

    if request.method == "POST" and form.is_valid():
        ids = {int(x) for x in request.POST.getlist("members") if x.isdigit()}
        selected = [m for m in members if m.pk in ids]
        if not selected:
            messages.error(request, "Aucun membre sélectionné.")
        else:
            rollover, report = services.launch(
                request, form.cleaned_data["target_season"], form.cleaned_data["subject"], form.cleaned_data["body"], selected
            )
            if report["sent"]:
                messages.success(request, f"{report['sent']} invitation(s) envoyée(s) pour la saison {rollover.target_season}.")
            if report["skipped"]:
                messages.info(request, f"{report['skipped']} membre(s) déjà invité(s) pour cette saison : pas de second envoi.")
            for problem in report["failed"]:
                messages.warning(request, problem)
            if dev_email_preview_enabled() and report["links"]:
                request.session[services.DEV_LINKS_SESSION_KEY] = report["links"]
            return redirect("renewals:rollover", pk=rollover.pk)

    rows = [(m, m.primary_email, m.pk in invited) for m in members]
    return render(
        request,
        "renewals/launch.html",
        {"form": form, "rows": rows, "season": season, "existing": existing, "rollovers": SeasonRollover.objects.all()[:10]},
    )


def rollover_detail(request, pk):
    rollover = get_object_or_404(SeasonRollover, pk=pk)
    requests_ = rollover.requests.select_related("member")
    counts = {status: 0 for status, _ in Status.choices}
    for r in requests_:
        counts[r.status] += 1
    return render(
        request,
        "renewals/rollover.html",
        {
            "rollover": rollover, "requests": requests_, "counts": counts, "Status": Status,
            "dev_links": request.session.pop(services.DEV_LINKS_SESSION_KEY, None) if dev_email_preview_enabled() else None,
        },
    )


def review(request, pk):
    req = get_object_or_404(RenewalRequest.objects.select_related("member", "rollover"), pk=pk)
    member = req.member
    billing_form = None
    if req.status == Status.TO_VALIDATE and member is not None:
        proposed_mode = req.proposed.get("training_mode", member.training_mode_id)
        billing_form = RenewalBillingForm(
            request.POST if request.POST.get("action") == "validate" else None,
            initial={"training_mode": proposed_mode or None, "tariff_bracket": member.tariff_bracket, "family_discount": member.family_discount},
        )

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "validate" and billing_form is not None and billing_form.is_valid():
                services.validate(req, request.user, billing_form.cleaned_data)
                messages.success(request, f"Données de {req.member_name} validées et enregistrées sur la fiche.")
                return redirect(member)
            if action == "confirm_resignation":
                if member is not None and request.POST.get("confirm") != member.member_id:
                    messages.error(request, "Confirmation incorrecte : recopiez l'ID de la fiche pour la supprimer.")
                    return redirect("renewals:review", pk=req.pk)
                kept = services.confirm_resignation(req, request.user)
                note = f" Ses {kept} facture(s) sont conservées dans la comptabilité." if kept else ""
                messages.success(request, f"Démission de {req.member_name} confirmée : fiche supprimée définitivement.{note}")
                return redirect("renewals:rollover", pk=req.rollover_id)
            if action == "keep":
                services.keep_member(req, request.user)
                messages.info(request, f"La fiche de {req.member_name} est conservée.")
                return redirect("renewals:rollover", pk=req.rollover_id)
        except services.RenewalError as exc:
            messages.error(request, str(exc))
            return redirect("renewals:review", pk=req.pk)

    return render(request, "renewals/review.html", {"req": req, "member": member, "billing_form": billing_form, "Status": Status})


@require_POST
def resend(request, pk):
    req = get_object_or_404(RenewalRequest.objects.select_related("member", "rollover"), pk=pk)
    try:
        link = services.resend(request, req)
        messages.success(request, f"Invitation renvoyée à {req.email} (l'ancien lien ne fonctionne plus).")
        if dev_email_preview_enabled():
            request.session[services.DEV_LINKS_SESSION_KEY] = [(req.member_name, link)]
    except services.RenewalError as exc:
        messages.error(request, str(exc))
    return redirect("renewals:rollover", pk=req.rollover_id)


# --- Public (lien personnel reçu par email) --------------------------------------------------------


def _privacy_notice():
    form = FormDefinition.objects.exclude(privacy_notice="").first()
    return form.privacy_notice if form else FormDefinition._meta.get_field("privacy_notice").default


def public_form(request, token):
    req = RenewalRequest.find(token)
    club = ClubSettings.load()
    if req is None:
        return render(request, "renewals/public_invalid.html", {"club": club, "reason": "invalid"}, status=404)
    if not req.is_open:
        reason = "answered" if req.status != Status.SENT else "expired"
        return render(request, "renewals/public_invalid.html", {"club": club, "reason": reason, "req": req}, status=410)

    member = req.member
    action = request.POST.get("action")
    if request.method == "POST" and action == "resign":
        if request.POST.get("confirm_resign") != "on":
            messages.error(request, "Cochez la case de confirmation pour annoncer la démission.")
            return redirect("renewals:public_form", token=token)
        services.submit_resignation(request, req, request.POST.get("resign_remark", ""))
        return render(request, "renewals/public_done.html", {"club": club, "req": req, "resigned": True})

    form = RenewalForm(member, request.POST if action == "confirm" else None)
    if action == "confirm" and form.is_valid():
        services.submit_update(request, req, form)
        return render(request, "renewals/public_done.html", {"club": club, "req": req, "resigned": False})
    return render(
        request,
        "renewals/public_form.html",
        {"club": club, "req": req, "member": member, "form": form, "privacy_notice": _privacy_notice()},
    )
