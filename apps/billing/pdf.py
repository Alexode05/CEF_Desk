"""
Génération du PDF de facture : en-tête professionnel du club (reportlab) + bloc QR-facture
normalisé produit par la bibliothèque `qrbill` (jamais redessiné à la main), converti en
dessin reportlab via svglib et placé en bas de page A4, conformément au gabarit SIX.
"""
import io
import re
import tempfile
from pathlib import Path

from qrbill import QRBill
from reportlab.graphics import renderPDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas
from svglib.svglib import svg2rlg

NAVY = colors.HexColor("#1b2a41")
GREY = colors.HexColor("#6b7a8c")
LINE = colors.HexColor("#d9dee7")


def split_street(address):
    """« Chemin des Vignes 4 » -> (« Chemin des Vignes », « 4ˊ) ; sinon (adresse, None)."""
    address = (address or "").strip()
    m = re.match(r"^(.*?)[\s,]+(\d+[a-zA-Z]?(?:\s*[-/]\s*\d+[a-zA-Z]?)?)$", address)
    if m and m.group(1):
        return m.group(1).strip(), m.group(2).strip()
    return address, None


def _clip(value, n):
    value = (value or "").strip()
    return value[:n]


def build_qrbill(club, invoice):
    """Objet QRBill à partir des paramètres du club (créancier) et de la facture (débiteur)."""
    c_street, c_num = split_street(club.street)
    d_street, d_num = split_street(invoice.debtor_street)
    creditor = {
        "name": _clip(club.creditor_name, 70),
        "street": _clip(c_street, 70),
        "pcode": _clip(club.postal_code, 16),
        "city": _clip(club.city, 35),
        "country": (club.country or "CH").upper(),
    }
    if c_num:
        creditor["house_num"] = _clip(c_num, 16)
    debtor = None
    if invoice.debtor_name:
        debtor = {
            "name": _clip(invoice.debtor_name, 70),
            "street": _clip(d_street, 70),
            "pcode": _clip(invoice.debtor_postal_code, 16),
            "city": _clip(invoice.debtor_city, 35),
            "country": (invoice.debtor_country or "CH").upper(),
        }
        if d_num:
            debtor["house_num"] = _clip(d_num, 16)
        if not debtor["street"] or not debtor["pcode"] or not debtor["city"]:
            debtor = None  # adresse incomplète : QR-facture sans débiteur (à compléter à la main)
    return QRBill(
        account=club.iban.replace(" ", ""),
        creditor=creditor,
        debtor=debtor,
        amount=f"{invoice.amount:.2f}",
        currency="CHF",
        reference_number=invoice.reference or None,
        additional_information=_clip(invoice.description, 140),
        language="fr",
    )


def render_invoice_pdf(club, invoice) -> bytes:
    bill = build_qrbill(club, invoice)
    with tempfile.TemporaryDirectory() as tmp:
        svg_path = Path(tmp) / "bill.svg"
        bill.as_svg(str(svg_path))
        drawing = svg2rlg(str(svg_path))

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    left = 20 * mm
    right = width - 20 * mm
    y = height - 20 * mm

    # --- En-tête club ---
    logo_h = 0
    if getattr(club, "logo", None):
        try:
            c.drawImage(club.logo.path, left, y - 18 * mm, width=36 * mm, height=18 * mm, preserveAspectRatio=True, anchor="nw", mask="auto")
            logo_h = 20 * mm
        except Exception:  # noqa: BLE001 — logo illisible : on continue sans
            logo_h = 0
    text_x = left + (40 * mm if logo_h else 0)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(text_x, y - 5 * mm, club.club_name)
    c.setFont("Helvetica", 9.5)
    c.setFillColor(GREY)
    c.drawString(text_x, y - 10.5 * mm, f"{club.street}, {club.postal_code} {club.city}")
    c.drawString(text_x, y - 15 * mm, f"IBAN {club.iban_formatted}")
    if club.treasurer_email:
        c.drawString(text_x, y - 19.5 * mm, f"Contact : {club.treasurer_email}")

    # Bloc « FACTURE » à droite
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 20)
    c.drawRightString(right, y - 5 * mm, "FACTURE")
    c.setFont("Helvetica", 9.5)
    c.setFillColor(GREY)
    c.drawRightString(right, y - 11 * mm, f"N° {invoice.number}")
    c.drawRightString(right, y - 15.5 * mm, f"Date d'émission : {invoice.issue_date.strftime('%d.%m.%Y')}")
    c.drawRightString(right, y - 20 * mm, f"Échéance : {invoice.due_date.strftime('%d.%m.%Y')}")

    c.setStrokeColor(LINE)
    c.setLineWidth(0.8)
    c.line(left, y - 26 * mm, right, y - 26 * mm)

    # --- Adresse du destinataire ---
    ay = y - 40 * mm
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10.5)
    lines = [invoice.debtor_name, invoice.debtor_street, f"{invoice.debtor_postal_code} {invoice.debtor_city}".strip()]
    if invoice.member.title:
        lines.insert(0, invoice.member.get_title_display())
    for i, line in enumerate(l for l in lines if l):
        c.drawString(right - 75 * mm, ay - i * 5 * mm, line)

    # --- Objet ---
    oy = y - 75 * mm
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 12)
    heading = invoice.description[:80] if invoice.is_manual else f"Cotisation — saison {invoice.season}"
    c.drawString(left, oy, heading)
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    c.drawString(left, oy - 6.5 * mm, f"Founex, le {invoice.issue_date.strftime('%d.%m.%Y')}")
    c.drawString(
        left,
        oy - 14 * mm,
        "Nous vous remercions de régler le montant ci-dessous au moyen de la QR-facture jointe, "
        f"d'ici au {invoice.due_date.strftime('%d.%m.%Y')}.",
    )

    # --- Tableau ---
    ty = oy - 26 * mm
    c.setFillColor(colors.HexColor("#f4f6f9"))
    c.rect(left, ty - 2 * mm, right - left, 8 * mm, stroke=0, fill=1)
    c.setFillColor(GREY)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(left + 3 * mm, ty + 0.5 * mm, "DÉSIGNATION")
    c.drawRightString(right - 3 * mm, ty + 0.5 * mm, "MONTANT CHF")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    row_y = ty - 8.5 * mm
    if invoice.is_manual:
        label = invoice.description
    else:
        label = f"Cotisation {invoice.season} — {invoice.member.display_name}"
        if invoice.training_mode_label:
            label += f" — {invoice.training_mode_label}"
        if invoice.bracket_label:
            label += f" ({invoice.bracket_label})"
    label_lines = (simpleSplit(label, "Helvetica", 10, right - left - 45 * mm) or [label])[:3]
    for n, line in enumerate(label_lines):
        c.drawString(left + 3 * mm, row_y - n * 4.6 * mm, line)
    c.drawRightString(right - 3 * mm, row_y, f"{invoice.base_amount:,.2f}".replace(",", "'"))
    row_y -= (len(label_lines) - 1) * 4.6 * mm
    if invoice.family_discount and invoice.family_discount > 0:
        row_y -= 6 * mm
        c.drawString(left + 3 * mm, row_y, "Réduction famille (2e enfant et suivants)")
        c.drawRightString(right - 3 * mm, row_y, f"-{invoice.family_discount:,.2f}".replace(",", "'"))
    row_y -= 4 * mm
    c.setStrokeColor(LINE)
    c.line(left, row_y, right, row_y)
    row_y -= 7 * mm
    c.setFont("Helvetica-Bold", 11.5)
    c.setFillColor(NAVY)
    c.drawString(left + 3 * mm, row_y, "TOTAL À PAYER")
    c.drawRightString(right - 3 * mm, row_y, f"CHF {invoice.amount:,.2f}".replace(",", "'"))

    c.setFillColor(GREY)
    c.setFont("Helvetica", 8.5)
    c.drawString(left, row_y - 12 * mm, f"Référence de paiement : {_format_reference(invoice.reference)}")
    c.drawString(left, row_y - 17 * mm, "Merci de conserver cette facture. Le comité du Cercle d'Escrime de Founex.")

    # --- Bloc QR-facture (normé, généré par qrbill) en bas de page ---
    renderPDF.draw(drawing, c, 0, 0)

    c.showPage()
    c.save()
    return buf.getvalue()


def _format_reference(ref):
    ref = (ref or "").replace(" ", "")
    if not ref:
        return "—"
    if ref.startswith("RF"):
        return " ".join(ref[i : i + 4] for i in range(0, len(ref), 4))
    # Référence QR : 27 chiffres groupés « 00 00000 00000 00000 00000 00000 »
    return ref[:2] + " " + " ".join(ref[i : i + 5] for i in range(2, len(ref), 5))
