from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDailySalesSummary(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company

    def _wizard(self):
        return self.env["daily.sales.summary.wizard"].create(
            {
                "date_from": fields.Date.to_date("2026-08-01"),
                "date_to": fields.Date.to_date("2026-08-07"),
                "company_id": self.company.id,
            }
        )

    def test_invalid_date_range_is_blocked(self):
        with self.assertRaises(ValidationError):
            self.env["daily.sales.summary.wizard"].create(
                {
                    "date_from": fields.Date.to_date("2026-08-07"),
                    "date_to": fields.Date.to_date("2026-08-01"),
                    "company_id": self.company.id,
                }
            )

    def test_empty_period_report_data(self):
        wizard = self._wizard()
        data = wizard._get_report_data()

        self.assertIn("payment_columns", data)
        self.assertIn("lines", data)
        self.assertNotIn("Unclassified", wizard._get_columns(data))
        self.assertNotIn("Write-Off", wizard._get_columns(data))

    def test_dynamic_payment_columns_use_channel_and_journal_names(self):
        channel = self.env["account.payment.channel"].create(
            {
                "name": "Unit Test Channel",
                "code": "UTC",
            }
        )
        wizard = self._wizard()
        payment_columns = wizard._get_payment_columns(
            {
                "used_channel_names": {channel.name},
                "used_journal_names": {"071 KPay", channel.name},
            }
        )
        columns = wizard._get_columns(
            {
                "payment_columns": payment_columns,
            }
        )

        self.assertIn(channel.name, columns)
        self.assertIn("071 KPay", columns)
        self.assertEqual(columns.count(channel.name), 1)
        self.assertNotIn("Unclassified", columns)
        self.assertNotIn("Write-Off", columns)
