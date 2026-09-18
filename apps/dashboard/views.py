from django.contrib import messages
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.billing.models import Invoice
from apps.members.models import Member, MemberStatus

from .forms import ClubSettingsForm, TodoForm
from .models import ClubSettings, DashboardNote, TodoItem, TodoLog


def index(request):
    club = ClubSettings.load()
    active_count = Member.objects.filter(status=MemberStatus.ACTIF).count()
    pending_members = Member.objects.filter(status=MemberStatus.EN_ATTENTE).order_by("-created_at")[:8]
    pending_count = Member.objects.filter(status=MemberStatus.EN_ATTENTE).count()
    unpaid = Invoice.objects.unpaid().select_related("member").order_by("issue_date")[:10]
    unpaid_count = Invoice.objects.unpaid().count()
    todos = TodoItem.objects.select_related("created_by", "done_by").all()[:50]
    return render(
        request,
        "dashboard/index.html",
        {
            "club": club,
            "active_count": active_count,
            "pending_members": pending_members,
            "pending_count": pending_count,
            "unpaid": unpaid,
            "unpaid_count": unpaid_count,
            "note": DashboardNote.load(),
            "todos": todos,
            "todo_form": TodoForm(),
            "todo_logs": TodoLog.objects.select_related("user")[:10],
        },
    )


@require_POST
def save_note(request):
    note = DashboardNote.load()
    note.content = request.POST.get("content", "")[:20000]
    note.updated_by = request.user
    note.save()
    return JsonResponse({"ok": True, "updated_at": timezone.localtime(note.updated_at).strftime("%d.%m.%Y %H:%M")})


@require_POST
def todo_add(request):
    form = TodoForm(request.POST)
    if form.is_valid():
        todo = TodoItem.objects.create(text=form.cleaned_data["text"], created_by=request.user, updated_by=request.user)
        TodoLog.objects.create(todo_text=todo.text, action="create", user=request.user)
    return redirect("dashboard:index")


@require_POST
def todo_toggle(request, pk):
    todo = get_object_or_404(TodoItem, pk=pk)
    todo.is_done = not todo.is_done
    todo.updated_by = request.user
    if todo.is_done:
        todo.done_at, todo.done_by = timezone.now(), request.user
        action = "done"
    else:
        todo.done_at, todo.done_by = None, None
        action = "undone"
    todo.save()
    TodoLog.objects.create(todo_text=todo.text, action=action, user=request.user)
    return redirect("dashboard:index")


@require_POST
def todo_edit(request, pk):
    todo = get_object_or_404(TodoItem, pk=pk)
    text = request.POST.get("text", "").strip()
    if not text:
        return HttpResponseBadRequest("Texte vide")
    todo.text = text[:300]
    todo.updated_by = request.user
    todo.save()
    TodoLog.objects.create(todo_text=todo.text, action="edit", user=request.user)
    return redirect("dashboard:index")


@require_POST
def todo_delete(request, pk):
    todo = get_object_or_404(TodoItem, pk=pk)
    TodoLog.objects.create(todo_text=todo.text, action="delete", user=request.user)
    todo.delete()
    return redirect("dashboard:index")


def club_settings(request):
    club = ClubSettings.load()
    form = ClubSettingsForm(request.POST or None, request.FILES or None, instance=club)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Paramètres du club enregistrés.")
        return redirect("dashboard:settings")
    return render(request, "dashboard/settings.html", {"form": form, "club": club})
