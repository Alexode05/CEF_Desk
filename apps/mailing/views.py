from django.contrib import messages
from django.core.mail import EmailMessage
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.utils import safe_next
from apps.billing.models import EmailLog
from apps.dashboard.models import ClubSettings
from apps.members.models import Member

from .forms import CampaignForm, MailingListForm
from .models import Campaign, MailingList


def index(request):
    lists = MailingList.objects.select_related("group").prefetch_related("static_members")
    return render(request, "mailing/index.html", {"lists": lists, "campaigns": Campaign.objects.select_related("mailing_list")[:15]})


def list_create(request):
    initial = {}
    ids = request.GET.get("ids")
    if ids:
        initial = {"kind": MailingList.Kind.STATIC, "ids": ids}
    form = MailingListForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        ml = form.save(commit=False)
        ml.created_by = request.user
        ml.save()
        if ml.kind == MailingList.Kind.STATIC:
            ml.static_members.set(Member.objects.filter(pk__in=form.member_ids()))
        messages.success(request, f"Liste « {ml.name} » créée ({ml.members().count()} contact(s)).")
        return redirect("mailing:list_detail", pk=ml.pk)
    preselected = Member.objects.filter(pk__in=[int(x) for x in (ids or "").split(",") if x.strip().isdigit()])
    return render(request, "mailing/list_form.html", {"form": form, "preselected": preselected})


@require_POST
def list_from_selection(request):
    """Crée une liste de diffusion statique à partir des contacts cochés dans la liste des Contacts."""
    ids = [int(x) for x in request.POST.get("ids", "").split(",") if x.strip().isdigit()]
    name = request.POST.get("name", "").strip()[:100]
    back = safe_next(request, "members:list")
    if not ids:
        messages.error(request, "Aucun contact sélectionné.")
        return redirect(back)
    if not name:
        messages.error(request, "Donnez un nom à la liste de diffusion.")
        return redirect(back)
    if MailingList.objects.filter(name__iexact=name).exists():
        messages.error(request, f"Une liste nommée « {name} » existe déjà : choisissez un autre nom.")
        return redirect(back)
    members = Member.objects.filter(pk__in=ids)
    ml = MailingList.objects.create(
        name=name, kind=MailingList.Kind.STATIC, description=request.POST.get("description", "").strip()[:200], created_by=request.user
    )
    ml.static_members.set(members)
    without_email = sum(1 for m in members if not m.primary_email)
    note = f" {without_email} n'ont pas d'adresse email et ne recevront rien." if without_email else ""
    messages.success(request, f"Liste « {ml.name} » créée avec {members.count()} contact(s).{note}")
    return redirect("mailing:list_detail", pk=ml.pk)


def list_detail(request, pk):
    ml = get_object_or_404(MailingList, pk=pk)
    form = MailingListForm(request.POST or None, instance=ml)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Liste modifiée.")
        return redirect("mailing:list_detail", pk=pk)
    members = ml.members().prefetch_related("groups")
    all_members = Member.objects.persons().order_by("last_name", "first_name") if ml.kind == MailingList.Kind.STATIC else None
    return render(request, "mailing/list_detail.html", {"ml": ml, "form": form, "members": members, "recipients": ml.recipients(), "all_members": all_members})


@require_POST
def list_set_members(request, pk):
    ml = get_object_or_404(MailingList, pk=pk, kind=MailingList.Kind.STATIC)
    ids = [int(x) for x in request.POST.getlist("member_ids") if x.isdigit()]
    ml.static_members.set(Member.objects.filter(pk__in=ids))
    messages.success(request, f"Sélection enregistrée ({len(ids)} contact(s)).")
    return redirect("mailing:list_detail", pk=pk)


@require_POST
def list_delete(request, pk):
    ml = get_object_or_404(MailingList, pk=pk)
    ml.delete()
    messages.success(request, f"Liste « {ml.name} » supprimée.")
    return redirect("mailing:index")


def campaign_compose(request):
    club = ClubSettings.load()
    initial = {"mailing_list": request.GET.get("list")}
    form = CampaignForm(request.POST or None, request.FILES or None, initial=initial)
    preview = None
    if request.method == "POST" and form.is_valid():
        ml = form.cleaned_data["mailing_list"]
        excluded = form.excluded()
        recipients = [(m, e) for m, e in ml.recipients() if m.pk not in excluded]
        if request.POST.get("confirm") == "1":
            campaign = Campaign(subject=form.cleaned_data["subject"], body=form.cleaned_data["body"], mailing_list=ml, sent_by=request.user)
            attachment = form.cleaned_data.get("attachment")
            if attachment:
                campaign.attachment = attachment
            campaign.save()
            att_bytes = None
            if attachment:
                attachment.seek(0)
                att_bytes = attachment.read()
            cc = [club.treasurer_email] if form.cleaned_data.get("cc_treasurer") and club.treasurer_email else []
            ok, ko = 0, 0
            for m, email in recipients:
                values = {"prenom": m.first_name, "nom": m.last_name, "club": club.club_name, "saison": club.current_season_label()}
                try:
                    subject = campaign.subject.format(**values)
                    body = campaign.body.format(**values)
                except (KeyError, IndexError, ValueError):
                    subject, body = campaign.subject, campaign.body
                msg = EmailMessage(subject=subject, body=body, to=[email], cc=cc)
                if att_bytes:
                    msg.attach(attachment.name, att_bytes, attachment.content_type or "application/octet-stream")
                log = EmailLog(kind="mailing", to=email, cc=", ".join(cc), subject=subject, member=m, sent_by=request.user)
                try:
                    msg.send(fail_silently=False)
                    ok += 1
                except Exception as exc:  # noqa: BLE001
                    log.ok, log.error = False, str(exc)
                    ko += 1
                log.save()
            campaign.recipients_count, campaign.errors_count = ok, ko
            campaign.save(update_fields=["recipients_count", "errors_count"])
            messages.success(request, f"Email envoyé à {ok} destinataire(s){f', {ko} échec(s)' if ko else ''}.")
            return redirect("mailing:index")
        preview = recipients
    return render(request, "mailing/compose.html", {"form": form, "preview": preview, "club": club})
