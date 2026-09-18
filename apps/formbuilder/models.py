"""
Module Formulaires — cahier des charges section 7 (option B : éditeur structuré).

Un formulaire = liste ordonnée de `FormField` : soit un champ de la fiche membre (référence à
`FieldDefinition`, donc synchronisé par construction avec la fiche), soit un bloc de texte
explicatif, soit le sélecteur spécial « type d'inscription » (Mineur / Majeur) qui pilote le
profil de la fiche créée et les règles conditionnelles.
"""
import json

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.members.models import ContactGroup, FieldDefinition, Member, Profile


class FormDefinition(models.Model):
    name = models.CharField("Nom", max_length=120)
    slug = models.SlugField("Adresse publique", max_length=80, unique=True, help_text="Fin du lien public : /formulaires/public/<adresse>/")
    is_active = models.BooleanField("Actif (accessible publiquement)", default=True)
    profile = models.CharField(
        "Profil de fiche créé", max_length=10, choices=Profile.choices, default=Profile.MAJEUR,
        help_text="Profil par défaut ; un champ « Type d'inscription » dans le formulaire peut le remplacer selon la réponse.",
    )
    intro_text = models.TextField("Texte d'introduction", blank=True)
    privacy_notice = models.TextField(
        "Mention de protection des données (LPD)",
        default=(
            "Les données saisies sont utilisées exclusivement par le comité du Cercle d'Escrime de Founex pour "
            "la gestion des inscriptions, des cours, des licences et de la facturation des cotisations. Elles ne sont "
            "transmises à aucun tiers en dehors des obligations liées à la licence fédérale. Vous pouvez demander leur "
            "consultation, correction ou suppression en écrivant au secrétariat du club."
        ),
    )
    success_message = models.TextField(
        "Message de confirmation", default="Merci ! Votre inscription a bien été transmise au comité, qui la validera prochainement et reviendra vers vous."
    )
    default_groups = models.ManyToManyField(ContactGroup, verbose_name="Groupes attribués automatiquement", blank=True)
    notify_email = models.EmailField("Email de notification (vide = secrétariat des paramètres)", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["name"]
        verbose_name = "formulaire"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "formulaire"
            slug, n = base, 1
            while FormDefinition.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f"{base}-{n}"
            self.slug = slug
        super().save(*args, **kwargs)

    def get_public_url(self):
        from django.urls import reverse

        return reverse("formbuilder:public", args=[self.slug])

    def export_definition(self):
        """Copie de référence (JSON) déposée dans l'espace de stockage."""
        return json.dumps(
            {
                "name": self.name,
                "slug": self.slug,
                "profile": self.profile,
                "intro_text": self.intro_text,
                "fields": [
                    {
                        "kind": f.kind,
                        "key": f.field_definition.key if f.field_definition else None,
                        "label": f.effective_label,
                        "required": f.required,
                        "help_text": f.help_text,
                        "text": f.text,
                        "condition": f.condition_description(),
                    }
                    for f in self.fields.all()
                ],
            },
            ensure_ascii=False,
            indent=2,
        )


class FormField(models.Model):
    class Kind(models.TextChoices):
        FIELD = "FIELD", "Champ de la fiche membre"
        TEXT = "TEXT", "Bloc de texte explicatif"
        PROFILE = "PROFILE", "Type d'inscription (Mineur / Majeur)"

    class Operator(models.TextChoices):
        EQ = "eq", "est égal à"
        NE = "ne", "est différent de"
        NOTEMPTY = "notempty", "est renseigné"
        CONTAINS = "contains", "contient"

    form = models.ForeignKey(FormDefinition, on_delete=models.CASCADE, related_name="fields")
    order = models.PositiveIntegerField(default=0)
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.FIELD)
    field_definition = models.ForeignKey(FieldDefinition, null=True, blank=True, on_delete=models.CASCADE)
    label = models.CharField("Libellé affiché (vide = libellé de la fiche)", max_length=150, blank=True)
    help_text = models.CharField("Aide", max_length=300, blank=True)
    text = models.TextField("Texte du bloc", blank=True)
    required = models.BooleanField("Obligatoire", default=False)

    condition_field = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="dependents", verbose_name="Afficher si le champ"
    )
    condition_operator = models.CharField(max_length=10, choices=Operator.choices, default=Operator.EQ, blank=True)
    condition_value = models.CharField("Valeur", max_length=150, blank=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "champ de formulaire"
        verbose_name_plural = "champs de formulaire"

    def __str__(self):
        return self.effective_label

    @property
    def input_name(self):
        return f"f{self.pk}"

    @property
    def effective_label(self):
        if self.label:
            return self.label
        if self.kind == self.Kind.PROFILE:
            return "Type d'inscription"
        if self.kind == self.Kind.TEXT:
            return (self.text or "Texte")[:40]
        if self.field_definition:
            from apps.members import fields as F

            bf = F.BUILTIN_BY_KEY.get(self.field_definition.key)
            return bf.label_for(self.form.profile) if bf else self.field_definition.label
        return "Champ"

    @property
    def is_input(self):
        return self.kind != self.Kind.TEXT

    def condition_description(self):
        if not self.condition_field_id:
            return ""
        op = self.get_condition_operator_display()
        if self.condition_operator == self.Operator.NOTEMPTY:
            return f"si « {self.condition_field.effective_label} » {op}"
        return f"si « {self.condition_field.effective_label} » {op} « {self.condition_value} »"

    def condition_met(self, values):
        """Évalue la règle côté serveur à partir des valeurs brutes soumises (dict input_name -> valeur)."""
        if not self.condition_field_id:
            return True
        actual = values.get(self.condition_field.input_name)
        if isinstance(actual, (list, tuple)):
            actual_l = [str(a).lower() for a in actual]
            joined = " ".join(actual_l)
        else:
            actual_l = [str(actual or "").lower()]
            joined = actual_l[0]
        expected = (self.condition_value or "").lower()
        op = self.condition_operator
        if op == self.Operator.NOTEMPTY:
            return bool(joined.strip())
        if op == self.Operator.EQ:
            return expected in actual_l
        if op == self.Operator.NE:
            return expected not in actual_l
        if op == self.Operator.CONTAINS:
            return expected in joined
        return True


class FormSubmission(models.Model):
    form = models.ForeignKey(FormDefinition, on_delete=models.SET_NULL, null=True, related_name="submissions")
    form_name = models.CharField(max_length=120)
    data = models.JSONField("Réponses", default=list)  # liste de {label, key, value}
    profile = models.CharField(max_length=10, choices=Profile.choices)
    member = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name="submissions")
    submitted_at = models.DateTimeField(auto_now_add=True)
    notified = models.BooleanField(default=False)
    notify_error = models.TextField(blank=True)

    class Meta:
        ordering = ["-submitted_at"]
        verbose_name = "soumission"

    def __str__(self):
        return f"{self.form_name} — {self.submitted_at:%d.%m.%Y %H:%M}"

    @property
    def summary_name(self):
        d = {row["key"]: row["value"] for row in self.data if row.get("key")}
        return f"{d.get('first_name', '')} {d.get('last_name', '')}".strip() or "—"
