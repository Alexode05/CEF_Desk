"""
Contrôle technique d'une facture générée : rastérise le PDF, décode le QR code et vérifie le
contenu décodé point par point contre les Swiss Implementation Guidelines QR-bill (v2.3).

    python manage.py check_qrbill            # dernière facture
    python manage.py check_qrbill 2027-0002  # facture précise

Ce contrôle NE REMPLACE PAS la validation sur le portail officiel SIX
(https://validation.iso-payments.ch — compte requis) : il sert de garde-fou automatique.
Dépendances de développement : `pip install -r requirements-dev.txt` (pymupdf, opencv-python-headless).
"""
import re

from django.core.management.base import BaseCommand, CommandError
from stdnum import iban as iban_mod
from stdnum import iso11649
from stdnum.ch import esr

from apps.billing.models import Invoice
from apps.billing.pdf import build_qrbill
from apps.dashboard.models import ClubSettings


def spec_checks(data):
    """Renvoie la liste des écarts à la norme (vide = conforme)."""
    lines = data.split("\r\n") if "\r\n" in data else data.split("\n")
    errs = []

    def chk(cond, msg):
        if not cond:
            errs.append(msg)

    chk(len(lines) >= 31, "Nombre de lignes insuffisant")
    if len(lines) < 31:
        return errs
    chk(lines[0] == "SPC", "QRType doit être SPC")
    chk(lines[1] == "0200", "Version doit être 0200")
    chk(lines[2] == "1", "Coding doit être 1 (UTF-8)")
    acct = lines[3]
    chk(len(acct) == 21 and acct[:2] in ("CH", "LI") and iban_mod.is_valid(acct), "IBAN invalide")
    chk(lines[4] == "S", "Adresse créancier structurée (S) obligatoire depuis IG 2.3")
    chk(0 < len(lines[5]) <= 70, "Nom créancier (1-70)")
    chk(len(lines[6]) <= 70 and len(lines[7]) <= 16, "Rue/n° créancier")
    chk(0 < len(lines[8]) <= 16 and 0 < len(lines[9]) <= 35 and len(lines[10]) == 2, "NPA/ville/pays créancier")
    chk(all(l == "" for l in lines[11:18]), "Créancier final : 7 lignes vides attendues")
    chk(re.fullmatch(r"\d{1,9}\.\d{2}", lines[18]) is not None, "Montant au format 0.00")
    chk(lines[19] in ("CHF", "EUR"), "Devise CHF/EUR")
    chk(lines[20] in ("S", ""), "Adresse débiteur structurée ou vide")
    if lines[20] == "S":
        chk(0 < len(lines[21]) <= 70 and 0 < len(lines[24]) <= 16 and 0 < len(lines[25]) <= 35 and len(lines[26]) == 2, "Champs débiteur")
    reftp, ref = lines[27], lines[28]
    is_qr_iban = acct[4:9].isdigit() and 30000 <= int(acct[4:9]) <= 31999
    if reftp == "QRR":
        chk(is_qr_iban, "QRR exige un QR-IBAN")
        chk(len(ref) == 27 and ref.isdigit() and esr.is_valid(ref), "Référence QR (27 chiffres, modulo 10)")
    elif reftp == "SCOR":
        chk(not is_qr_iban, "SCOR interdit avec un QR-IBAN")
        chk(iso11649.is_valid(ref), "Référence SCOR (ISO 11649) invalide")
    elif reftp == "NON":
        chk(ref == "" and not is_qr_iban, "NON : référence vide et IBAN classique")
    else:
        errs.append("RefTp inconnu")
    chk(len(lines[29]) <= 140, "Message non structuré ≤ 140")
    chk(lines[30] == "EPD", "Trailer EPD attendu")
    chk(len(data) <= 997, "Charge utile ≤ 997 caractères")
    return errs


class Command(BaseCommand):
    help = "Décode le QR d'une facture PDF et vérifie sa conformité à la norme QR-facture."

    def add_arguments(self, parser):
        parser.add_argument("number", nargs="?", help="Numéro de facture (défaut : la plus récente)")

    def handle(self, *args, **options):
        try:
            import cv2
            import numpy as np
            import pymupdf
        except ImportError as exc:
            raise CommandError("Installez les dépendances de développement : pip install -r requirements-dev.txt") from exc

        inv = Invoice.objects.filter(number=options["number"]).first() if options["number"] else Invoice.objects.order_by("-id").first()
        if inv is None or not inv.pdf:
            raise CommandError("Facture introuvable ou sans PDF.")

        page = pymupdf.open(inv.pdf.path)[0]
        pix = page.get_pixmap(dpi=300)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR if pix.n == 4 else cv2.COLOR_RGB2BGR)
        data, pts, _ = cv2.QRCodeDetector().detectAndDecode(img)
        if not data:
            raise CommandError("QR code non décodable dans le PDF.")

        expected = build_qrbill(ClubSettings.load(), inv).qr_data()
        self.stdout.write(f"Facture {inv.number} — page {page.rect.width / 72 * 25.4:.0f}×{page.rect.height / 72 * 25.4:.0f} mm")
        self.stdout.write(f"QR décodé : {len(data)} caractères ; identique à la charge utile qrbill : {data.strip() == expected.strip()}")
        if pts is not None and len(pts):
            p = pts.reshape(-1, 2)
            mm = 300 / 25.4
            self.stdout.write(f"QR : {(p[:, 0].max() - p[:, 0].min()) / mm:.1f} mm de côté (norme : 46 mm), bord gauche à {p[:, 0].min() / mm:.1f} mm (norme : 67 mm)")
        errs = spec_checks(data)
        if errs:
            for e in errs:
                self.stderr.write(f" ✗ {e}")
            raise CommandError("Écarts détectés.")
        self.stdout.write(self.style.SUCCESS("Contenu conforme aux contrôles automatiques. Reste à valider sur le portail SIX (compte requis)."))
