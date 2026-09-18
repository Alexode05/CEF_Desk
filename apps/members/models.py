"""
Module Contacts / Membres — cahier des charges section 4.

Trois profils de fiche (Mineur, Majeur, Essai) partagent une même table `Member` ;
le jeu de champs visible/éditable dépend du profil (cf. `fields.py`). Les champs
personnalisés ajoutés depuis l'interface sont stockés dans `custom_data` (JSON) et
décrits par `FieldDefinition`, registre commun aux fiches, à la liste, aux exports
et à l'éditeur de formulaires.
"""
from django.conf import settings
from django.db import models

from . import services


class Profile(models.TextChoices):
    MINEUR = "MINEUR", "Mineur"
    MAJEUR = "MAJEUR", "Majeur"
    ESSAI = "ESSAI", "Cours d'essai"


class ContactKind(models.TextChoices):
    PERSONNE = "PERSONNE", "Personne"
    ENTREPRISE = "ENTREPRISE", "Entreprise"


class MemberStatus(models.TextChoices):
    ACTIF = "ACTIF", "Actif"
    LICENCE = "LICENCE", "Licence uniquement"
    ESSAI = "ESSAI", "Essai"
    EN_ATTENTE = "EN_ATTENTE", "En attente de validation"
    INACTIF = "INACTIF", "Inactif / sorti"


class Title(models.TextChoices):
    MONSIEUR = "MONSIEUR", "Monsieur"
    MADAME = "MADAME", "Madame"
    FAMILLE = "FAMILLE", "Famille"
    AUX_PARENTS = "AUX_PARENTS", "Aux parents de"


class Sex(models.TextChoices):
    M = "M", "Masculin"
    F = "F", "Féminin"
    AUTRE = "AUTRE", "Autre"


class Laterality(models.TextChoices):
    DROITE = "DROITE", "Droite"
    GAUCHE = "GAUCHE", "Gauche"


WEEKDAYS = [
    ("LUN", "Lundi"),
    ("MAR", "Mardi"),
    ("MER", "Mercredi"),
    ("JEU", "Jeudi"),
    ("VEN", "Vendredi"),
]
WEEKDAY_LABELS = dict(WEEKDAYS)

# Liste de pays/nationalités courants (code ISO -> libellé). Extensible.
COUNTRIES = [
    ("CH", "Suisse"),
    ("FR", "France"),
    ("DE", "Allemagne"),
    ("IT", "Italie"),
    ("AT", "Autriche"),
    ("LI", "Liechtenstein"),
    ("BE", "Belgique"),
    ("LU", "Luxembourg"),
    ("NL", "Pays-Bas"),
    ("ES", "Espagne"),
    ("PT", "Portugal"),
    ("GB", "Royaume-Uni"),
    ("IE", "Irlande"),
    ("US", "États-Unis"),
    ("CA", "Canada"),
    ("BR", "Brésil"),
    ("RU", "Russie"),
    ("UA", "Ukraine"),
    ("PL", "Pologne"),
    ("CZ", "Tchéquie"),
    ("HU", "Hongrie"),
    ("RO", "Roumanie"),
    ("GR", "Grèce"),
    ("TR", "Turquie"),
    ("SE", "Suède"),
    ("NO", "Norvège"),
    ("DK", "Danemark"),
    ("FI", "Finlande"),
    ("CN", "Chine"),
    ("JP", "Japon"),
    ("KR", "Corée du Sud"),
    ("IN", "Inde"),
    ("AU", "Australie"),
    ("MA", "Maroc"),
    ("TN", "Tunisie"),
    ("DZ", "Algérie"),
    ("EG", "Égypte"),
    ("ZA", "Afrique du Sud"),
    ("AR", "Argentine"),
    ("MX", "Mexique"),
    ("XX", "Autre"),
]
COUNTRY_LABELS = dict(COUNTRIES)

NATIONALITIES = [
    ("CH", "Suisse"),
    ("FR", "Française"),
    ("DE", "Allemande"),
    ("IT", "Italienne"),
    ("AT", "Autrichienne"),
    ("LI", "Liechtensteinoise"),
    ("BE", "Belge"),
    ("LU", "Luxembourgeoise"),
    ("NL", "Néerlandaise"),
    ("ES", "Espagnole"),
    ("PT", "Portugaise"),
    ("GB", "Britannique"),
    ("IE", "Irlandaise"),
    ("US", "Américaine"),
    ("CA", "Canadienne"),
    ("BR", "Brésilienne"),
    ("RU", "Russe"),
    ("UA", "Ukrainienne"),
    ("PL", "Polonaise"),
    ("CZ", "Tchèque"),
    ("HU", "Hongroise"),
    ("RO", "Roumaine"),
    ("GR", "Grecque"),
    ("TR", "Turque"),
    ("SE", "Suédoise"),
    ("NO", "Norvégienne"),
    ("DK", "Danoise"),
    ("FI", "Finlandaise"),
    ("CN", "Chinoise"),
    ("JP", "Japonaise"),
    ("KR", "Sud-coréenne"),
    ("IN", "Indienne"),
    ("AU", "Australienne"),
    ("MA", "Marocaine"),
    ("TN", "Tunisienne"),
    ("DZ", "Algérienne"),
    ("EG", "Égyptienne"),
    ("ZA", "Sud-africaine"),
    ("AR", "Argentine"),
    ("MX", "Mexicaine"),
    ("XX", "Autre"),
]
NATIONALITY_LABELS = dict(NATIONALITIES)


class ContactGroup(models.Model):
    """Groupe secondaire (cours, Essais, Comité, sponsors…), créé librement par le comité."""

    name = models.CharField("Nom", max_length=80, unique=True)
    description = models.CharField("Description", max_length=200, blank=True)
    sort_order = models.PositiveSmallIntegerField("Ordre", default=100)
    is_course = models.BooleanField(
        "Groupe de cours", default=False, help_text="Cochez pour les groupes correspondant à un créneau de cours."
    )

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "groupe"

    def __str__(self):
        return self.name


class TrainingMode(models.Model):
    """Modalité d'entraînement (nombre de jours/semaine) — base du barème (section 5)."""

    name = models.CharField("Nom", max_length=80, unique=True)
    days_per_week = models.PositiveSmallIntegerField("Jours par semaine", default=1)
    sort_order = models.PositiveSmallIntegerField("Ordre", default=100)
    is_active = models.BooleanField("Active", default=True)

    class Meta:
        ordering = ["sort_order", "days_per_week"]
        verbose_name = "modalité d'entraînement"
        verbose_name_plural = "modalités d'entraînement"

    def __str__(self):
        return self.name


class TariffBracket(models.Model):
    """Tranche tarifaire : P'tit Zorros, Moins de 20 ans, Dès 20 ans, Étudiant 20-25 ans."""

    name = models.CharField("Nom", max_length=80, unique=True)
    sort_order = models.PositiveSmallIntegerField("Ordre", default=100)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "tranche tarifaire"
        verbose_name_plural = "tranches tarifaires"

    def __str__(self):
        return self.name


class MemberQuerySet(models.QuerySet):
    def members(self):
        return self.filter(
            kind=ContactKind.PERSONNE, status__in=[MemberStatus.ACTIF, MemberStatus.LICENCE, MemberStatus.ESSAI]
        )

    def non_members(self):
        return self.filter(kind=ContactKind.PERSONNE).exclude(
            status__in=[MemberStatus.ACTIF, MemberStatus.LICENCE, MemberStatus.ESSAI]
        )

    def persons(self):
        return self.filter(kind=ContactKind.PERSONNE)

    def companies(self):
        return self.filter(kind=ContactKind.ENTREPRISE)


class Member(models.Model):
    objects = MemberQuerySet.as_manager()

    # --- Nature de la fiche ---
    profile = models.CharField("Profil", max_length=10, choices=Profile.choices, default=Profile.MAJEUR)
    kind = models.CharField("Type de contact", max_length=12, choices=ContactKind.choices, default=ContactKind.PERSONNE)
    company_name = models.CharField("Raison sociale", max_length=120, blank=True)

    # --- Identité et adresse ---
    title = models.CharField("Titre", max_length=12, choices=Title.choices, blank=True)
    first_name = models.CharField("Prénom", max_length=80)
    last_name = models.CharField("Nom", max_length=80)
    address = models.CharField("Adresse", max_length=150, blank=True)
    postal_code = models.CharField("Code postal", max_length=16, blank=True)
    city = models.CharField("Ville", max_length=80, blank=True)
    country = models.CharField("Pays", max_length=2, choices=COUNTRIES, default="CH", blank=True)
    sex = models.CharField("Sexe", max_length=6, choices=Sex.choices, blank=True)
    birth_date = models.DateField("Date de naissance", null=True, blank=True)
    nationality = models.CharField("Nationalité", max_length=2, choices=NATIONALITIES, blank=True)

    # --- Adhésion ---
    entry_date = models.DateField("Entrée", null=True, blank=True)
    exit_date = models.DateField("Sortie", null=True, blank=True)
    status = models.CharField("Statut", max_length=12, choices=MemberStatus.choices, default=MemberStatus.EN_ATTENTE)
    member_id = models.SlugField("ID", max_length=120, unique=True, blank=True)
    role = models.CharField("Rôle", max_length=80, blank=True, help_text="Ex. Direction, Comité, Entraîneur…")

    # --- Escrime ---
    avs_number = models.CharField("N° AVS", max_length=16, blank=True, help_text="Format 756.XXXX.XXXX.XX")
    laterality = models.CharField("Latéralité", max_length=6, choices=Laterality.choices, blank=True)
    licence_number = models.CharField("N° de licence", max_length=40, blank=True)

    # --- Contact ---
    phone = models.CharField("Téléphone élève", max_length=30, blank=True)
    phone_parent1 = models.CharField("Téléphone parent 1", max_length=30, blank=True)
    phone_parent2 = models.CharField("Téléphone parent 2", max_length=30, blank=True)
    email = models.EmailField("Email", blank=True)
    email_alt = models.EmailField("Email alternative", blank=True)
    email_parent1 = models.EmailField("Email parent 1", blank=True)
    email_parent2 = models.EmailField("Email parent 2", blank=True)

    # --- Entraînement / facturation ---
    groups = models.ManyToManyField(ContactGroup, verbose_name="Groupes", blank=True, related_name="members")
    training_mode = models.ForeignKey(
        TrainingMode, verbose_name="Modalité d'entraînement", null=True, blank=True, on_delete=models.SET_NULL
    )
    training_days = models.JSONField("Jours d'entraînement", default=list, blank=True)
    tariff_bracket = models.ForeignKey(
        TariffBracket,
        verbose_name="Tranche tarifaire",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Complétée par le comité à la validation de l'inscription.",
    )
    family_discount = models.BooleanField(
        "Réduction famille (2ᵉ enfant et suivants)",
        default=False,
        help_text="-100 CHF sur la cotisation. Cochée par le comité à la validation.",
    )

    # --- Divers ---
    notes = models.TextField("Remarques internes", blank=True)
    custom_data = models.JSONField("Champs personnalisés", default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="members_created"
    )

    class Meta:
        ordering = ["last_name", "first_name"]
        verbose_name = "contact"

    def __str__(self):
        return self.display_name

    # --- Sauvegarde : ID auto + cohérence profil Essai ---
    def save(self, *args, **kwargs):
        if self.profile == Profile.ESSAI and self.status not in (MemberStatus.EN_ATTENTE, MemberStatus.INACTIF):
            self.status = MemberStatus.ESSAI
        if not self.member_id:
            self.member_id = services.generate_member_id(
                self.first_name, self.last_name, exclude_pk=self.pk, company_name=self.company_name
            )
        self.training_days = [d for d in (self.training_days or []) if d in WEEKDAY_LABELS]
        super().save(*args, **kwargs)

    # --- Propriétés d'affichage ---
    @property
    def display_name(self):
        if self.kind == ContactKind.ENTREPRISE and self.company_name:
            return self.company_name
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_company(self):
        return self.kind == ContactKind.ENTREPRISE

    @property
    def primary_email(self):
        """Email de facturation/contact principal : élève, sinon parent 1, sinon alternative."""
        return self.email or self.email_parent1 or self.email_alt or self.email_parent2

    @property
    def all_emails(self):
        return [e for e in [self.email, self.email_parent1, self.email_parent2, self.email_alt] if e]

    @property
    def age(self):
        return services.age_on(self.birth_date)

    @property
    def category(self):
        if self.profile == Profile.ESSAI:
            return ""
        return services.age_category(self.birth_date)

    @property
    def training_days_display(self):
        return ", ".join(WEEKDAY_LABELS.get(d, d) for d in self.training_days or [])

    @property
    def avs_masked(self):
        if not self.avs_number:
            return ""
        return "756.****.****." + self.avs_number.replace(".", "")[-2:]

    @property
    def base_tariff(self):
        """Montant du barème pour (modalité, tranche), ou None si non défini."""
        from apps.billing.models import Tariff

        if not self.training_mode_id or not self.tariff_bracket_id:
            return None
        return Tariff.amount_for(self.training_mode_id, self.tariff_bracket_id)

    @property
    def tariff_for_mode(self):
        """Tarif affiché à côté de la modalité : celui de la tranche si connue, sinon la grille de la modalité."""
        from apps.billing.models import Tariff

        if not self.training_mode_id:
            return None
        if self.tariff_bracket_id:
            return Tariff.amount_for(self.training_mode_id, self.tariff_bracket_id)
        return None

    @property
    def computed_amount(self):
        return services.compute_contribution(self.base_tariff, self.family_discount)

    @property
    def latest_invoice(self):
        return self.invoices.order_by("-issue_date", "-id").first()

    @property
    def invoice_status_label(self):
        inv = self.latest_invoice
        return inv.get_status_display() if inv else "Aucune facture"

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("members:detail", args=[self.pk])


class FieldType(models.TextChoices):
    TEXT = "TEXT", "Texte court"
    TEXTAREA = "TEXTAREA", "Texte long"
    EMAIL = "EMAIL", "Email"
    PHONE = "PHONE", "Téléphone"
    DATE = "DATE", "Date"
    SELECT = "SELECT", "Liste déroulante (choix unique)"
    MULTISELECT = "MULTISELECT", "Sélecteur multiple"
    WEEKDAYS = "WEEKDAYS", "Jours de la semaine"
    BOOLEAN = "BOOLEAN", "Case à cocher (oui/non)"
    NUMBER = "NUMBER", "Nombre"


class FieldDefinition(models.Model):
    """
    Registre des champs de la fiche membre.

    - `is_builtin=True` : champ natif du modèle `Member` (clé = nom de l'attribut).
    - `is_builtin=False` : champ personnalisé créé depuis l'UI, stocké dans `Member.custom_data[key]`.
    Sert de source unique pour : l'affichage/édition des fiches, le sélecteur de colonnes,
    les filtres, l'export CSV et l'éditeur de formulaires (section 7).
    """

    key = models.SlugField("Clé technique", max_length=60, unique=True)
    label = models.CharField("Libellé", max_length=100)
    field_type = models.CharField("Type", max_length=12, choices=FieldType.choices, default=FieldType.TEXT)
    choices = models.JSONField(
        "Options", default=list, blank=True, help_text="Pour les listes : une option par ligne."
    )
    profiles = models.JSONField(
        "Profils concernés", default=list, blank=True, help_text="Liste parmi MINEUR, MAJEUR, ESSAI (vide = tous)."
    )
    is_builtin = models.BooleanField("Champ natif", default=False, editable=False)
    is_sensitive = models.BooleanField(
        "Donnée sensible", default=False, help_text="Masquée par défaut dans les listes et exclue des exports par défaut."
    )
    is_active = models.BooleanField("Actif", default=True)
    sort_order = models.PositiveSmallIntegerField("Ordre", default=500)
    help_text = models.CharField("Aide", max_length=200, blank=True)

    class Meta:
        ordering = ["sort_order", "label"]
        verbose_name = "champ de fiche"
        verbose_name_plural = "champs de fiche"

    def __str__(self):
        return self.label

    def applies_to(self, profile):
        return not self.profiles or profile in self.profiles

    @property
    def choice_pairs(self):
        return [(c, c) for c in self.choices or []]


class SavedView(models.Model):
    """Vue personnalisée de la liste des contacts (colonnes + filtres), partagée par le comité."""

    name = models.CharField("Nom", max_length=80)
    columns = models.JSONField(default=list, blank=True)
    filters = models.JSONField(default=list, blank=True)
    category = models.CharField(max_length=20, blank=True)
    group = models.ForeignKey(ContactGroup, null=True, blank=True, on_delete=models.SET_NULL)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "vue enregistrée"

    def __str__(self):
        return self.name


class UserListPreference(models.Model):
    """Colonnes choisies par chaque utilisateur pour la liste des contacts."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="list_preference")
    columns = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Colonnes de {self.user}"
