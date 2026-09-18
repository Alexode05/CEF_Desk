from django.test import TestCase

from apps.exports.views import build_csv


class CsvVariantTests(TestCase):
    headers = ["Prénom", "Ville"]
    rows = [["Léa", "Genève"], ["Noé", "Café-sur-Mer"]]

    def test_excel_windows_variant(self):
        payload = build_csv(self.headers, self.rows, "excel")
        self.assertTrue(payload.startswith(b"\xef\xbb\xbf"))  # BOM UTF-8
        text = payload.decode("utf-8-sig")
        self.assertIn("Prénom;Ville\r\n", text)
        self.assertIn("Léa;Genève\r\n", text)

    def test_macos_variant(self):
        payload = build_csv(self.headers, self.rows, "macos")
        self.assertFalse(payload.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(payload.decode("utf-8"), "Prénom;Ville\nLéa;Genève\nNoé;Café-sur-Mer\n")

    def test_numbers_variant(self):
        payload = build_csv(self.headers, self.rows, "numbers")
        self.assertEqual(payload.decode("utf-8"), "Prénom,Ville\nLéa,Genève\nNoé,Café-sur-Mer\n")
