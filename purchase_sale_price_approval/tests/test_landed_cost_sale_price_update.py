from odoo import fields
from odoo.tests.common import TransactionCase


class TestLandedCostSalePriceUpdate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency = cls.company.currency_id
        cls.uom = cls.env.ref("uom.product_uom_unit")
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.product = cls.env["product.product"].create(
            {
                "name": "Landed Cost Test Product",
                "type": "consu",
                "uom_id": cls.uom.id,
                "uom_po_id": cls.uom.id,
                "list_price": 100.0,
            }
        )
        cls.move = cls.env["stock.move"].create(
            {
                "name": "Test Landed Cost Move",
                "product_id": cls.product.id,
                "product_uom": cls.uom.id,
                "product_uom_qty": 10.0,
                "location_id": cls.stock_location.id,
                "location_dest_id": cls.customer_location.id,
                "company_id": cls.company.id,
            }
        )
        cls.rule = cls.env["sale.price.rule"].create(
            {
                "name": "Landed Cost Test Rule",
                "company_id": cls.company.id,
                "currency_id": cls.currency.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "apply_on": "all",
                            "from_amount": 0.0,
                            "to_amount": 0.0,
                            "markup_type": "fixed",
                            "markup_value": 30.0,
                            "valid_from": "2026-01-01",
                        },
                    )
                ],
            }
        )
        cls.rule.action_activate()

    def _create_done_landed_cost(self, former_cost=1000.0, additional_costs=None):
        landed_cost = self.env["stock.landed.cost"].create(
            {
                "date": fields.Date.context_today(self.env["stock.landed.cost"]),
                "company_id": self.company.id,
                "state": "done",
            }
        )
        for additional_cost in additional_costs or [200.0]:
            self.env["stock.valuation.adjustment.lines"].create(
                {
                    "cost_id": landed_cost.id,
                    "move_id": self.move.id,
                    "product_id": self.product.id,
                    "quantity": 10.0,
                    "former_cost": former_cost,
                    "additional_landed_cost": additional_cost,
                }
            )
        return landed_cost

    def test_purchase_order_generator_is_disabled(self):
        purchase_order = self.env["purchase.order"].new({})
        self.assertFalse(purchase_order._generate_pending_sale_price_updates())

    def test_landed_cost_creates_pending_update_for_price_increase(self):
        landed_cost = self._create_done_landed_cost()
        landed_cost._generate_sale_price_updates_from_landed_cost()

        update = self.env["sale.price.update"].search([("landed_cost_id", "=", landed_cost.id)])
        self.assertEqual(len(update), 1)
        self.assertEqual(update.state, "pending")
        self.assertEqual(update.cost_source, "landed_cost")
        self.assertAlmostEqual(update.landed_unit_cost, 120.0)
        self.assertAlmostEqual(update.calculated_sale_price, 150.0)
        self.assertAlmostEqual(self.product.product_tmpl_id.list_price, 100.0)

    def test_equal_or_lower_price_does_not_create_update(self):
        self.product.product_tmpl_id.list_price = 150.0
        landed_cost = self._create_done_landed_cost()
        landed_cost._generate_sale_price_updates_from_landed_cost()

        update = self.env["sale.price.update"].search([("landed_cost_id", "=", landed_cost.id)])
        self.assertFalse(update)

    def test_duplicate_generation_does_not_create_duplicate_update(self):
        landed_cost = self._create_done_landed_cost()
        landed_cost._generate_sale_price_updates_from_landed_cost()
        landed_cost._generate_sale_price_updates_from_landed_cost()

        updates = self.env["sale.price.update"].search([("landed_cost_id", "=", landed_cost.id)])
        self.assertEqual(len(updates), 1)

    def test_multiple_adjustment_lines_use_weighted_landed_unit_cost(self):
        landed_cost = self._create_done_landed_cost(former_cost=1000.0, additional_costs=[100.0, 100.0])
        landed_cost._generate_sale_price_updates_from_landed_cost()

        update = self.env["sale.price.update"].search([("landed_cost_id", "=", landed_cost.id)])
        self.assertEqual(len(update), 1)
        self.assertAlmostEqual(update.landed_unit_cost, 120.0)
        self.assertAlmostEqual(update.calculated_sale_price, 150.0)

    def test_stale_pending_update_is_cancelled_when_price_not_higher(self):
        landed_cost = self._create_done_landed_cost()
        pending_update = self.env["sale.price.update"].create(
            {
                "company_id": self.company.id,
                "currency_id": self.currency.id,
                "landed_cost_id": landed_cost.id,
                "product_id": self.product.id,
                "purchase_quantity": 10.0,
                "purchase_uom_id": self.uom.id,
                "purchase_price": 120.0,
                "source_currency_id": self.currency.id,
                "landed_unit_cost": 120.0,
                "converted_purchase_price": 120.0,
                "old_sale_price": 100.0,
                "markup_type": "fixed",
                "markup_value": 30.0,
                "calculated_sale_price": 150.0,
                "approved_sale_price": 150.0,
                "rule_line_id": self.rule.line_ids.id,
                "effective_date": fields.Date.context_today(self),
                "cost_source": "landed_cost",
            }
        )
        self.product.product_tmpl_id.list_price = 150.0

        landed_cost._generate_sale_price_updates_from_landed_cost()

        self.assertEqual(pending_update.state, "cancelled")

    def test_approved_update_is_not_cancelled_when_price_not_higher(self):
        landed_cost = self._create_done_landed_cost()
        approved_update = self.env["sale.price.update"].create(
            {
                "company_id": self.company.id,
                "currency_id": self.currency.id,
                "landed_cost_id": landed_cost.id,
                "product_id": self.product.id,
                "purchase_quantity": 10.0,
                "purchase_uom_id": self.uom.id,
                "purchase_price": 120.0,
                "source_currency_id": self.currency.id,
                "landed_unit_cost": 120.0,
                "converted_purchase_price": 120.0,
                "old_sale_price": 100.0,
                "markup_type": "fixed",
                "markup_value": 30.0,
                "calculated_sale_price": 150.0,
                "approved_sale_price": 150.0,
                "rule_line_id": self.rule.line_ids.id,
                "effective_date": fields.Date.context_today(self),
                "cost_source": "landed_cost",
            }
        )
        approved_update.with_context(skip_sale_price_update_protection=True).write({"state": "approved"})
        self.product.product_tmpl_id.list_price = 150.0

        landed_cost._generate_sale_price_updates_from_landed_cost()

        self.assertEqual(approved_update.state, "approved")
