"""Widgets de formulaire propres à CEF Desk."""
from django import forms
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe


class RoleBadgesWidget(forms.Widget):
    """
    Sélecteur de rôles multiples : on choisit un rôle dans la liste, il apparaît en dessous sous forme
    de badge que l'on peut retirer (×). Chaque badge porte un champ caché du même nom : le serveur
    reçoit donc simplement la liste des rôles retenus. Le comportement JavaScript est dans cefdesk.js.
    """

    choices = ()

    def value_from_datadict(self, data, files, name):
        return data.getlist(name) if hasattr(data, "getlist") else data.get(name)

    def value_omitted_from_data(self, data, files, name):
        # Aucun badge = « aucun rôle » : ne pas conserver l'ancienne valeur.
        return False

    def render(self, name, value, attrs=None, renderer=None):
        labels = dict(self.choices)
        selected = [v for v in (value or []) if v in labels]
        select_id = (attrs or {}).get("id", f"id_{name}")
        options = format_html_join(
            "",
            '<option value="{}"{}>{}</option>',
            ((code, mark_safe(" disabled") if code in selected else "", label) for code, label in self.choices),
        )
        badges = format_html_join(
            "",
            '<span class="badge role-badge" data-value="{0}">{1}'
            '<button type="button" class="role-badge-remove" aria-label="Retirer le rôle {1}" title="Retirer">&times;</button>'
            '<input type="hidden" name="{2}" value="{0}"></span>',
            ((code, labels[code], name) for code in selected),
        )
        return format_html(
            '<div class="role-picker" data-name="{name}">'
            '<select class="form-select role-picker-select" id="{sid}"><option value="">— ajouter un rôle —</option>{options}</select>'
            '<div class="role-picker-badges mt-2">{badges}</div></div>',
            name=name, sid=select_id, options=options, badges=badges,
        )
