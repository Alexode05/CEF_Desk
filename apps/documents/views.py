import mimetypes

from django.conf import settings
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Folder, StoredFile

FORBIDDEN_EXTENSIONS = {"exe", "bat", "cmd", "com", "msi", "scr", "ps1", "vbs", "js", "jar", "sh"}


def index(request):
    folder = None
    folder_id = request.GET.get("folder")
    if folder_id:
        folder = get_object_or_404(Folder, pk=folder_id)
    subfolders = Folder.objects.filter(parent=folder)
    files = StoredFile.objects.filter(folder=folder).select_related("uploaded_by") if folder else StoredFile.objects.none()
    return render(
        request,
        "documents/index.html",
        {
            "folder": folder,
            "ancestors": folder.ancestors() if folder else [],
            "subfolders": subfolders,
            "files": files,
            "max_mb": settings.DOCUMENTS_MAX_UPLOAD_MB,
        },
    )


@require_POST
def upload(request, folder_pk):
    folder = get_object_or_404(Folder, pk=folder_pk)
    count = 0
    for f in request.FILES.getlist("files"):
        ext = f.name.rsplit(".", 1)[-1].lower() if "." in f.name else ""
        if ext in FORBIDDEN_EXTENSIONS:
            messages.error(request, f"« {f.name} » : type de fichier non autorisé.")
            continue
        if f.size > settings.DOCUMENTS_MAX_UPLOAD_MB * 1024 * 1024:
            messages.error(request, f"« {f.name} » dépasse {settings.DOCUMENTS_MAX_UPLOAD_MB} Mo.")
            continue
        name = f.name
        n = 1
        while StoredFile.objects.filter(folder=folder, name=name).exists():
            n += 1
            stem, dot, ext2 = f.name.rpartition(".")
            name = f"{stem or ext2} ({n}).{ext2}" if dot else f"{f.name} ({n})"
        StoredFile.objects.create(
            folder=folder, name=name, file=f, size=f.size,
            content_type=f.content_type or mimetypes.guess_type(name)[0] or "", uploaded_by=request.user,
        )
        count += 1
    if count:
        messages.success(request, f"{count} fichier(s) déposé(s) dans {folder.path}.")
    return redirect(f"{redirect('documents:index').url}?folder={folder.pk}")


def download(request, pk):
    stored = get_object_or_404(StoredFile, pk=pk)
    inline = request.GET.get("inline") == "1"
    try:
        response = FileResponse(stored.file.open("rb"), content_type=stored.content_type or "application/octet-stream")
    except FileNotFoundError:
        raise Http404("Fichier introuvable sur le disque")
    disposition = "inline" if inline else "attachment"
    response["Content-Disposition"] = f'{disposition}; filename="{stored.name}"'
    return response


@require_POST
def create_folder(request, parent_pk=None):
    parent = get_object_or_404(Folder, pk=parent_pk) if parent_pk else None
    name = request.POST.get("name", "").strip().replace("/", "-")
    if not name:
        messages.error(request, "Nom de dossier vide.")
    elif Folder.objects.filter(parent=parent, name=name).exists():
        messages.error(request, "Un dossier de ce nom existe déjà ici.")
    else:
        folder = Folder.objects.create(name=name, parent=parent)
        messages.success(request, f"Dossier « {folder.path} » créé.")
    target = f"?folder={parent.pk}" if parent else ""
    return redirect(f"{redirect('documents:index').url}{target}")


@require_POST
def rename(request, kind, pk):
    name = request.POST.get("name", "").strip().replace("/", "-")
    if not name:
        messages.error(request, "Nom vide.")
        return redirect("documents:index")
    if kind == "folder":
        obj = get_object_or_404(Folder, pk=pk)
        if obj.is_system:
            messages.error(request, "Les dossiers système (Club, Direction, Public) ne peuvent pas être renommés.")
            return redirect(f"{redirect('documents:index').url}?folder={obj.parent_id or ''}")
        obj.name = name
        obj.save()
        back = obj.parent_id
    else:
        obj = get_object_or_404(StoredFile, pk=pk)
        obj.name = name
        obj.save()
        back = obj.folder_id
    messages.success(request, "Renommé.")
    return redirect(f"{redirect('documents:index').url}?folder={back or ''}")


@require_POST
def delete(request, kind, pk):
    if kind == "folder":
        obj = get_object_or_404(Folder, pk=pk)
        if obj.is_system:
            messages.error(request, "Les dossiers système ne peuvent pas être supprimés.")
            return redirect("documents:index")
        if obj.children.exists() or obj.files.exists():
            messages.error(request, "Le dossier n'est pas vide : supprimez d'abord son contenu.")
            return redirect(f"{redirect('documents:index').url}?folder={obj.pk}")
        back = obj.parent_id
        obj.delete()
    else:
        obj = get_object_or_404(StoredFile, pk=pk)
        back = obj.folder_id
        obj.file.delete(save=False)
        obj.delete()
    messages.success(request, "Supprimé définitivement.")
    return redirect(f"{redirect('documents:index').url}?folder={back or ''}")
