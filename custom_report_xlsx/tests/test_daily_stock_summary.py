from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDailyStockSummary(TransactionCase):
    def test_defaults_and_columns(self):
        wizard = self.env["daily.stock.summary.wizard"].create({})

        self.assertEqual(wizard.date, fields.Date.context_today(wizard))
        self.assertFalse(wizard.location_ids)
        self.assertEqual(
            wizard._get_columns(),
            [
                "No.",
                "Product",
                "Engine",
                "Brand",
                "Location",
                "UoM",
                "Opening Qty",
                "Receipt In",
                "Delivery Out",
                "Internal In",
                "Internal Out",
                "Closing Qty",
            ],
        )

    def test_empty_location_filter_uses_all_internal_locations(self):
        wizard = self.env["daily.stock.summary.wizard"].create({})
        locations = wizard._get_report_locations()

        self.assertTrue(all(location.usage == "internal" for location in locations))
        self.assertTrue(
            all(
                not location.company_id or location.company_id == wizard.company_id
                for location in locations
            )
        )
