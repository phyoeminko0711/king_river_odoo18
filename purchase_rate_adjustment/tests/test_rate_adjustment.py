from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestPurchaseRateAdjustment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].set_param("product.weight_in_lbs", "0")
        cls.rate_b = cls.env["product.rate.scheme"].create(
            {"name": "Test B Rate", "code": "B"}
        )
        cls.rate_c = cls.env["product.rate.scheme"].create(
            {"name": "Test C Rate", "code": "C"}
        )
        cls.product_b = cls.env["product.template"].create(
            {
                "name": "Test B Product",
                "rate_scheme_id": cls.rate_b.id,
                "weight": 2.0,
                "list_price": 100.0,
            }
        )
        cls.product_c = cls.env["product.template"].create(
            {
                "name": "Test C Product",
                "rate_scheme_id": cls.rate_c.id,
                "weight": 3.0,
                "list_price": 200.0,
            }
        )
        cls.other_product = cls.env["product.template"].create(
            {"name": "Test Other Product", "weight": 4.0, "list_price": 300.0}
        )

    def _wizard(self, rates, amount):
        return self.env["purchase.rate.adjustment.wizard"].create(
            {
                "rate_ids": [(6, 0, rates.ids)],
                "amount_per_kg": amount,
            }
        )

    def test_adjustment_updates_only_matching_product_sale_prices(self):
        wizard = self._wizard(self.rate_b | self.rate_c, 10.0)
        wizard.action_apply()

        self.assertEqual(self.product_b.list_price, 120.0)
        self.assertEqual(self.product_c.list_price, 230.0)
        self.assertEqual(self.other_product.list_price, 300.0)
        history = self.env["purchase.rate.adjustment"].search(
            [("rate_ids", "in", (self.rate_b | self.rate_c).ids)]
        )
        self.assertEqual(len(history), 1)
        self.assertEqual(history.rate_ids, self.rate_b | self.rate_c)
        self.assertEqual(history.amount_per_kg, 10.0)
        self.assertEqual(history.user_id, self.env.user)
        self.assertEqual(history.product_count, 2)

        with self.assertRaisesRegex(UserError, "already been applied"):
            wizard.action_apply()
        self.assertEqual(self.product_b.list_price, 120.0)

    def test_new_negative_adjustment_reduces_current_sale_price(self):
        self._wizard(self.rate_b, 10.0).action_apply()
        self._wizard(self.rate_b, -5.0).action_apply()
        self.assertEqual(self.product_b.list_price, 110.0)
        self.assertEqual(
            self.env["purchase.rate.adjustment"].search_count(
                [("rate_ids", "in", self.rate_b.ids)]
            ),
            2,
        )

    def test_weight_in_pounds_is_converted_to_kg(self):
        self.env["ir.config_parameter"].set_param("product.weight_in_lbs", "1")
        self._wizard(self.rate_b, 10.0).action_apply()
        weight_kg = self.env.ref("uom.product_uom_lb")._compute_quantity(
            self.product_b.weight, self.env.ref("uom.product_uom_kgm"), round=False
        )
        expected = self.env.company.currency_id.round(100.0 + weight_kg * 10.0)
        self.assertEqual(self.product_b.list_price, expected)

    def test_negative_sale_price_rolls_back_adjustment(self):
        wizard = self._wizard(self.rate_b, -100.0)
        with self.assertRaisesRegex(ValidationError, "negative"):
            wizard.action_apply()
        self.assertEqual(self.product_b.list_price, 100.0)
        self.assertFalse(
            self.env["purchase.rate.adjustment"].search(
                [("rate_ids", "in", self.rate_b.ids)]
            )
        )

    def test_missing_product_weight_blocks_entire_adjustment(self):
        self.product_c.weight = 0.0
        wizard = self._wizard(self.rate_b | self.rate_c, 10.0)
        with self.assertRaisesRegex(ValidationError, "positive weight"):
            wizard.action_apply()
        self.assertEqual(self.product_b.list_price, 100.0)
        self.assertEqual(self.product_c.list_price, 200.0)

    def test_history_is_not_directly_editable(self):
        with self.assertRaisesRegex(UserError, "wizard only"):
            self.env["purchase.rate.adjustment"].create(
                {
                    "rate_ids": [(6, 0, self.rate_b.ids)],
                    "amount_per_kg": 10.0,
                    "company_id": self.env.company.id,
                    "user_id": self.env.user.id,
                }
            )
