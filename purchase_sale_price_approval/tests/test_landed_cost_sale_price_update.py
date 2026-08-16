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

    def _create_foreign_currency(self, name, currency_name):
        currency = self.env["res.currency"].create(
            {
                "name": name,
                "currency_unit_label": currency_name,
                "currency_subunit_label": "%s Cent" % currency_name,
                "symbol": name,
                "rounding": 0.01,
                "decimal_places": 2,
                "active": True,
            }
        )
        return currency

    def _set_company_rate(self, currency, date, company_value):
        self.env["res.currency.rate"].create(
            {
                "name": date,
                "currency_id": currency.id,
                "company_id": self.company.id,
                "rate": 1.0 / company_value,
            }
        )

    def _create_company_rate(self, currency, date, company_value, trigger=True):
        rate_model = self.env["res.currency.rate"]
        if not trigger:
            rate_model = rate_model.with_context(skip_currency_sale_price_revaluation=True)
        return rate_model.create(
            {
                "name": date,
                "currency_id": currency.id,
                "company_id": self.company.id,
                "rate": 1.0 / company_value,
            }
        )

    def _create_foreign_purchase_line(self, product, currency, price_unit, date="2026-08-15"):
        vendor = self.env["res.partner"].create({"name": "Foreign Vendor %s" % currency.name})
        purchase_order = self.env["purchase.order"].create(
            {
                "partner_id": vendor.id,
                "currency_id": currency.id,
                "company_id": self.company.id,
                "date_order": date,
            }
        )
        purchase_line = self.env["purchase.order.line"].create(
            {
                "order_id": purchase_order.id,
                "product_id": product.id,
                "name": product.display_name,
                "product_qty": 1.0,
                "product_uom": product.uom_id.id,
                "price_unit": price_unit,
                "date_planned": date,
            }
        )
        return purchase_order, purchase_line

    def _create_approved_foreign_landed_source(
        self,
        product,
        currency,
        purchase_line,
        foreign_price=1.0,
        rate=4000.0,
        landed_cost=1000.0,
        markup=20.0,
        date="2026-08-15",
        sale_price=6000.0,
    ):
        purchase_cost = foreign_price * rate
        cost_basis = purchase_cost + landed_cost
        product.product_tmpl_id.list_price = sale_price
        return self.env["sale.price.update"].create(
            {
                "company_id": self.company.id,
                "currency_id": self.currency.id,
                "purchase_order_id": purchase_line.order_id.id,
                "purchase_order_line_id": purchase_line.id,
                "product_id": product.id,
                "purchase_quantity": purchase_line.product_qty,
                "purchase_uom_id": product.uom_id.id,
                "purchase_price": foreign_price,
                "source_currency_id": currency.id,
                "foreign_purchase_unit_price": foreign_price,
                "original_conversion_date": date,
                "original_currency_value": rate,
                "original_purchase_cost_company": purchase_cost,
                "landed_cost_unit_amount": landed_cost,
                "original_total_cost": cost_basis,
                "last_revaluation_date": date,
                "last_revaluation_rate": rate,
                "last_revalued_cost": cost_basis,
                "last_sale_price": sale_price,
                "previous_exchange_rate_value": rate,
                "current_exchange_rate_value": rate,
                "previous_converted_purchase_cost": purchase_cost,
                "current_converted_purchase_cost": purchase_cost,
                "landed_unit_cost": cost_basis,
                "converted_purchase_price": cost_basis,
                "old_sale_price": 0.0,
                "markup_type": "percentage",
                "markup_value": markup,
                "calculated_sale_price": sale_price,
                "approved_sale_price": sale_price,
                "rule_line_id": self.rule.line_ids.id,
                "effective_date": date,
                "conversion_date": date,
                "approved_by": self.env.user.id,
                "approved_date": fields.Datetime.now(),
                "state": "approved",
                "cost_source": "landed_cost",
            }
        )

    def _run_revaluation(self, date):
        return self.env["sale.price.update"].with_context(
            revaluation_date=fields.Date.from_string(date)
        )._cron_currency_sale_price_revaluation()

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

    def test_currency_revaluation_uses_context_date_and_prevents_duplicates(self):
        usd = self._create_foreign_currency("XCU", "Test USD")
        self._set_company_rate(usd, "2026-08-15", 4000.0)
        self._set_company_rate(usd, "2026-08-16", 5000.0)
        purchase_order, purchase_line = self._create_foreign_purchase_line(
            self.product,
            usd,
            1.0,
        )
        source = self._create_approved_foreign_landed_source(
            self.product,
            usd,
            purchase_line,
        )

        self.assertAlmostEqual(source.original_total_cost, 5000.0)
        self.assertAlmostEqual(source.approved_sale_price, 6000.0)

        self._run_revaluation("2026-08-16")

        revaluation = self.env["sale.price.update"].search(
            [
                ("product_id", "=", self.product.id),
                ("cost_source", "=", "currency_revaluation"),
                ("revaluation_date", "=", fields.Date.from_string("2026-08-16")),
            ]
        )
        self.assertEqual(len(revaluation), 1)
        self.assertAlmostEqual(revaluation.current_exchange_rate_value, 5000.0)
        self.assertAlmostEqual(revaluation.current_converted_purchase_cost, 5000.0)
        self.assertAlmostEqual(revaluation.landed_cost_unit_amount, 1000.0)
        self.assertAlmostEqual(revaluation.revalued_cost_basis, 6000.0)
        self.assertAlmostEqual(revaluation.approved_sale_price, 7200.0)
        self.assertAlmostEqual(self.product.product_tmpl_id.list_price, 7200.0)

        self._run_revaluation("2026-08-16")

        revaluations = self.env["sale.price.update"].search(
            [
                ("product_id", "=", self.product.id),
                ("cost_source", "=", "currency_revaluation"),
                ("revaluation_date", "=", fields.Date.from_string("2026-08-16")),
            ]
        )
        self.assertEqual(len(revaluations), 1)

    def test_currency_revaluation_skips_decrease_and_uses_latest_baseline(self):
        usd = self._create_foreign_currency("XDV", "Test USD")
        self._set_company_rate(usd, "2026-08-15", 4000.0)
        self._set_company_rate(usd, "2026-08-16", 5000.0)
        self._set_company_rate(usd, "2026-08-17", 4500.0)
        self._set_company_rate(usd, "2026-08-18", 5500.0)
        _purchase_order, purchase_line = self._create_foreign_purchase_line(
            self.product,
            usd,
            1.0,
        )
        self._create_approved_foreign_landed_source(
            self.product,
            usd,
            purchase_line,
        )
        self._run_revaluation("2026-08-16")
        self.assertAlmostEqual(self.product.product_tmpl_id.list_price, 7200.0)

        self._run_revaluation("2026-08-17")
        self.assertAlmostEqual(self.product.product_tmpl_id.list_price, 7200.0)
        decrease_revaluation = self.env["sale.price.update"].search(
            [
                ("product_id", "=", self.product.id),
                ("cost_source", "=", "currency_revaluation"),
                ("revaluation_date", "=", fields.Date.from_string("2026-08-17")),
            ]
        )
        self.assertFalse(decrease_revaluation)

        self._run_revaluation("2026-08-18")
        increase_revaluation = self.env["sale.price.update"].search(
            [
                ("product_id", "=", self.product.id),
                ("cost_source", "=", "currency_revaluation"),
                ("revaluation_date", "=", fields.Date.from_string("2026-08-18")),
            ]
        )
        self.assertEqual(len(increase_revaluation), 1)
        self.assertAlmostEqual(increase_revaluation.revalued_cost_basis, 6500.0)
        self.assertAlmostEqual(increase_revaluation.approved_sale_price, 7800.0)
        self.assertAlmostEqual(self.product.product_tmpl_id.list_price, 7800.0)

    def test_newer_approved_landed_cost_replaces_old_revaluation_basis(self):
        usd = self._create_foreign_currency("XNB", "Test USD")
        self._set_company_rate(usd, "2026-08-15", 4000.0)
        self._set_company_rate(usd, "2026-08-16", 5000.0)
        self._set_company_rate(usd, "2026-08-18", 5500.0)
        _purchase_order, first_line = self._create_foreign_purchase_line(
            self.product,
            usd,
            1.0,
        )
        self._create_approved_foreign_landed_source(
            self.product,
            usd,
            first_line,
        )
        self._run_revaluation("2026-08-16")

        _new_purchase_order, new_line = self._create_foreign_purchase_line(
            self.product,
            usd,
            1.2,
            date="2026-08-17",
        )
        self._create_approved_foreign_landed_source(
            self.product,
            usd,
            new_line,
            foreign_price=1.2,
            rate=5000.0,
            landed_cost=1000.0,
            date="2026-08-17",
            sale_price=8400.0,
        )
        self._run_revaluation("2026-08-18")

        latest = self.env["sale.price.update"].search(
            [
                ("product_id", "=", self.product.id),
                ("cost_source", "=", "currency_revaluation"),
                ("revaluation_date", "=", fields.Date.from_string("2026-08-18")),
            ],
            limit=1,
        )
        self.assertEqual(latest.purchase_order_line_id, new_line)
        self.assertAlmostEqual(latest.current_converted_purchase_cost, 6600.0)
        self.assertAlmostEqual(latest.revalued_cost_basis, 7600.0)
        self.assertAlmostEqual(latest.approved_sale_price, 9120.0)

    def test_multiple_foreign_currencies_revalue_independently(self):
        usd = self._create_foreign_currency("XMU", "Test USD")
        eur = self._create_foreign_currency("XME", "Test EUR")
        product_two = self.env["product.product"].create(
            {
                "name": "Second Currency Product",
                "type": "consu",
                "uom_id": self.uom.id,
                "uom_po_id": self.uom.id,
                "list_price": 6000.0,
            }
        )
        self._set_company_rate(usd, "2026-08-15", 4000.0)
        self._set_company_rate(usd, "2026-08-16", 5000.0)
        self._set_company_rate(eur, "2026-08-15", 3000.0)
        self._set_company_rate(eur, "2026-08-16", 3500.0)
        _usd_po, usd_line = self._create_foreign_purchase_line(self.product, usd, 1.0)
        _eur_po, eur_line = self._create_foreign_purchase_line(product_two, eur, 1.0)
        self._create_approved_foreign_landed_source(self.product, usd, usd_line)
        self._create_approved_foreign_landed_source(
            product_two,
            eur,
            eur_line,
            rate=3000.0,
            landed_cost=1000.0,
            sale_price=4800.0,
        )

        self._run_revaluation("2026-08-16")

        updates = self.env["sale.price.update"].search(
            [("cost_source", "=", "currency_revaluation")]
        )
        self.assertIn(self.product, updates.product_id)
        self.assertIn(product_two, updates.product_id)
        self.assertAlmostEqual(self.product.product_tmpl_id.list_price, 7200.0)
        self.assertAlmostEqual(product_two.product_tmpl_id.list_price, 5400.0)

    def test_invalid_legacy_and_company_currency_sources_are_skipped(self):
        usd = self._create_foreign_currency("XLG", "Test USD")
        self._set_company_rate(usd, "2026-08-15", 4000.0)
        self._set_company_rate(usd, "2026-08-16", 5000.0)
        _purchase_order, purchase_line = self._create_foreign_purchase_line(
            self.product,
            usd,
            1.0,
        )
        self._create_approved_foreign_landed_source(
            self.product,
            usd,
            purchase_line,
            foreign_price=5000.0,
            sale_price=6000.0,
        )
        company_product = self.env["product.product"].create(
            {
                "name": "Company Currency Source Product",
                "type": "consu",
                "uom_id": self.uom.id,
                "uom_po_id": self.uom.id,
                "list_price": 6000.0,
            }
        )
        company_po, company_line = self._create_foreign_purchase_line(
            company_product,
            self.currency,
            4000.0,
        )
        self.env["sale.price.update"].create(
            {
                "company_id": self.company.id,
                "currency_id": self.currency.id,
                "purchase_order_id": company_po.id,
                "purchase_order_line_id": company_line.id,
                "product_id": company_product.id,
                "purchase_quantity": 1.0,
                "purchase_uom_id": self.uom.id,
                "purchase_price": 4000.0,
                "source_currency_id": self.currency.id,
                "foreign_purchase_unit_price": 4000.0,
                "original_conversion_date": "2026-08-15",
                "original_currency_value": 1.0,
                "original_purchase_cost_company": 4000.0,
                "landed_cost_unit_amount": 1000.0,
                "original_total_cost": 5000.0,
                "landed_unit_cost": 5000.0,
                "converted_purchase_price": 5000.0,
                "old_sale_price": 0.0,
                "markup_type": "percentage",
                "markup_value": 20.0,
                "calculated_sale_price": 6000.0,
                "approved_sale_price": 6000.0,
                "rule_line_id": self.rule.line_ids.id,
                "effective_date": "2026-08-15",
                "conversion_date": "2026-08-15",
                "approved_by": self.env.user.id,
                "approved_date": fields.Datetime.now(),
                "state": "approved",
                "cost_source": "landed_cost",
            }
        )

        self._run_revaluation("2026-08-16")

        revaluations = self.env["sale.price.update"].search(
            [("cost_source", "=", "currency_revaluation")]
        )
        self.assertFalse(revaluations)
        self.assertAlmostEqual(self.product.product_tmpl_id.list_price, 6000.0)
        self.assertAlmostEqual(company_product.product_tmpl_id.list_price, 6000.0)

    def test_currency_rate_create_triggers_revaluation_without_cron(self):
        usd = self._create_foreign_currency("XEA", "Event USD")
        self._create_company_rate(usd, "2026-08-15", 4000.0, trigger=False)
        _purchase_order, purchase_line = self._create_foreign_purchase_line(self.product, usd, 1.0)
        self._create_approved_foreign_landed_source(self.product, usd, purchase_line)

        self._create_company_rate(usd, "2026-08-16", 5000.0)

        revaluation = self.env["sale.price.update"].search(
            [
                ("product_id", "=", self.product.id),
                ("cost_source", "=", "currency_revaluation"),
                ("revaluation_date", "=", fields.Date.from_string("2026-08-16")),
            ]
        )
        self.assertEqual(len(revaluation), 1)
        self.assertEqual(revaluation.state, "approved")
        self.assertAlmostEqual(revaluation.current_exchange_rate_value, 5000.0)
        self.assertAlmostEqual(revaluation.approved_sale_price, 7200.0)
        self.assertAlmostEqual(self.product.product_tmpl_id.list_price, 7200.0)

    def test_currency_rate_create_same_effective_rate_does_not_duplicate(self):
        usd = self._create_foreign_currency("XEB", "Event USD")
        self._create_company_rate(usd, "2026-08-15", 4000.0, trigger=False)
        _purchase_order, purchase_line = self._create_foreign_purchase_line(self.product, usd, 1.0)
        self._create_approved_foreign_landed_source(self.product, usd, purchase_line)
        self._create_company_rate(usd, "2026-08-16", 5000.0)

        self._create_company_rate(usd, "2026-08-16", 5000.0)

        revaluations = self.env["sale.price.update"].search(
            [
                ("product_id", "=", self.product.id),
                ("cost_source", "=", "currency_revaluation"),
                ("revaluation_date", "=", fields.Date.from_string("2026-08-16")),
            ]
        )
        self.assertEqual(len(revaluations), 1)
        self.assertAlmostEqual(self.product.product_tmpl_id.list_price, 7200.0)

    def test_currency_rate_decrease_does_not_lower_sale_price(self):
        usd = self._create_foreign_currency("XEC", "Event USD")
        self._create_company_rate(usd, "2026-08-15", 4000.0, trigger=False)
        _purchase_order, purchase_line = self._create_foreign_purchase_line(self.product, usd, 1.0)
        self._create_approved_foreign_landed_source(self.product, usd, purchase_line)
        self._create_company_rate(usd, "2026-08-16", 5000.0)

        self._create_company_rate(usd, "2026-08-17", 4500.0)

        decrease_revaluation = self.env["sale.price.update"].search(
            [
                ("product_id", "=", self.product.id),
                ("cost_source", "=", "currency_revaluation"),
                ("revaluation_date", "=", fields.Date.from_string("2026-08-17")),
            ]
        )
        self.assertFalse(decrease_revaluation)
        self.assertAlmostEqual(self.product.product_tmpl_id.list_price, 7200.0)

    def test_currency_rate_later_increase_uses_latest_revaluation_basis(self):
        usd = self._create_foreign_currency("XED", "Event USD")
        self._create_company_rate(usd, "2026-08-15", 4000.0, trigger=False)
        _purchase_order, purchase_line = self._create_foreign_purchase_line(self.product, usd, 1.0)
        self._create_approved_foreign_landed_source(self.product, usd, purchase_line)
        self._create_company_rate(usd, "2026-08-16", 5000.0)
        self._create_company_rate(usd, "2026-08-17", 4500.0)

        self._create_company_rate(usd, "2026-08-18", 5500.0)

        increase_revaluation = self.env["sale.price.update"].search(
            [
                ("product_id", "=", self.product.id),
                ("cost_source", "=", "currency_revaluation"),
                ("revaluation_date", "=", fields.Date.from_string("2026-08-18")),
            ]
        )
        self.assertEqual(len(increase_revaluation), 1)
        self.assertAlmostEqual(increase_revaluation.revalued_cost_basis, 6500.0)
        self.assertAlmostEqual(increase_revaluation.approved_sale_price, 7800.0)
        self.assertAlmostEqual(self.product.product_tmpl_id.list_price, 7800.0)

    def test_currency_rate_change_only_revalues_matching_currency_products(self):
        usd = self._create_foreign_currency("XEE", "Event USD")
        thb = self._create_foreign_currency("XEF", "Event THB")
        product_two = self.env["product.product"].create(
            {
                "name": "THB Event Product",
                "type": "consu",
                "uom_id": self.uom.id,
                "uom_po_id": self.uom.id,
                "list_price": 4800.0,
            }
        )
        self._create_company_rate(usd, "2026-08-15", 4000.0, trigger=False)
        self._create_company_rate(thb, "2026-08-15", 3000.0, trigger=False)
        _usd_po, usd_line = self._create_foreign_purchase_line(self.product, usd, 1.0)
        _thb_po, thb_line = self._create_foreign_purchase_line(product_two, thb, 1.0)
        self._create_approved_foreign_landed_source(self.product, usd, usd_line)
        self._create_approved_foreign_landed_source(
            product_two,
            thb,
            thb_line,
            rate=3000.0,
            landed_cost=1000.0,
            sale_price=4800.0,
        )

        self._create_company_rate(usd, "2026-08-16", 5000.0)

        updates = self.env["sale.price.update"].search(
            [("cost_source", "=", "currency_revaluation")]
        )
        self.assertIn(self.product, updates.product_id)
        self.assertNotIn(product_two, updates.product_id)
        self.assertAlmostEqual(self.product.product_tmpl_id.list_price, 7200.0)
        self.assertAlmostEqual(product_two.product_tmpl_id.list_price, 4800.0)

    def test_currency_rate_write_triggers_revaluation(self):
        usd = self._create_foreign_currency("XEG", "Event USD")
        self._create_company_rate(usd, "2026-08-15", 4000.0, trigger=False)
        _purchase_order, purchase_line = self._create_foreign_purchase_line(self.product, usd, 1.0)
        self._create_approved_foreign_landed_source(self.product, usd, purchase_line)
        rate = self._create_company_rate(usd, "2026-08-16", 4000.0, trigger=False)

        rate.write({"rate": 1.0 / 5000.0})

        revaluation = self.env["sale.price.update"].search(
            [
                ("product_id", "=", self.product.id),
                ("cost_source", "=", "currency_revaluation"),
                ("revaluation_date", "=", fields.Date.from_string("2026-08-16")),
            ]
        )
        self.assertEqual(len(revaluation), 1)
        self.assertAlmostEqual(revaluation.approved_sale_price, 7200.0)

    def test_currency_rate_write_date_uses_new_effective_date(self):
        usd = self._create_foreign_currency("XEH", "Event USD")
        self._create_company_rate(usd, "2026-08-15", 4000.0, trigger=False)
        _purchase_order, purchase_line = self._create_foreign_purchase_line(self.product, usd, 1.0)
        self._create_approved_foreign_landed_source(self.product, usd, purchase_line)
        rate = self._create_company_rate(usd, "2026-08-17", 4500.0, trigger=False)

        rate.write({"name": "2026-08-18", "rate": 1.0 / 5500.0})

        revaluation = self.env["sale.price.update"].search(
            [
                ("product_id", "=", self.product.id),
                ("cost_source", "=", "currency_revaluation"),
                ("revaluation_date", "=", fields.Date.from_string("2026-08-18")),
            ]
        )
        self.assertEqual(len(revaluation), 1)
        self.assertAlmostEqual(revaluation.current_exchange_rate_value, 5500.0)
        self.assertAlmostEqual(revaluation.approved_sale_price, 7800.0)

    def test_company_specific_currency_rate_only_revalues_that_company(self):
        usd = self._create_foreign_currency("XEI", "Event USD")
        company_two = self.env["res.company"].create({"name": "Second Revaluation Company"})
        rule_two = self.env["sale.price.rule"].create(
            {
                "name": "Second Company Rule",
                "company_id": company_two.id,
                "currency_id": self.currency.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "apply_on": "all",
                            "from_amount": 0.0,
                            "to_amount": 0.0,
                            "markup_type": "percentage",
                            "markup_value": 20.0,
                            "valid_from": "2026-01-01",
                        },
                    )
                ],
            }
        )
        rule_two.action_activate()
        product_two = self.env["product.product"].create(
            {
                "name": "Second Company Currency Product",
                "type": "consu",
                "uom_id": self.uom.id,
                "uom_po_id": self.uom.id,
                "list_price": 6000.0,
            }
        )
        self._create_company_rate(usd, "2026-08-15", 4000.0, trigger=False)
        self.env["res.currency.rate"].with_context(skip_currency_sale_price_revaluation=True).create(
            {
                "name": "2026-08-15",
                "currency_id": usd.id,
                "company_id": company_two.id,
                "rate": 1.0 / 4000.0,
            }
        )
        _po_one, line_one = self._create_foreign_purchase_line(self.product, usd, 1.0)
        vendor_two = self.env["res.partner"].create({"name": "Second Company Vendor"})
        po_two = self.env["purchase.order"].create(
            {
                "partner_id": vendor_two.id,
                "currency_id": usd.id,
                "company_id": company_two.id,
                "date_order": "2026-08-15",
            }
        )
        line_two = self.env["purchase.order.line"].create(
            {
                "order_id": po_two.id,
                "product_id": product_two.id,
                "name": product_two.display_name,
                "product_qty": 1.0,
                "product_uom": product_two.uom_id.id,
                "price_unit": 1.0,
                "date_planned": "2026-08-15",
            }
        )
        self._create_approved_foreign_landed_source(self.product, usd, line_one)
        purchase_cost = 4000.0
        landed_cost = 1000.0
        sale_price = 6000.0
        self.env["sale.price.update"].create(
            {
                "company_id": company_two.id,
                "currency_id": self.currency.id,
                "purchase_order_id": po_two.id,
                "purchase_order_line_id": line_two.id,
                "product_id": product_two.id,
                "purchase_quantity": 1.0,
                "purchase_uom_id": product_two.uom_id.id,
                "purchase_price": 1.0,
                "source_currency_id": usd.id,
                "foreign_purchase_unit_price": 1.0,
                "original_conversion_date": "2026-08-15",
                "original_currency_value": 4000.0,
                "original_purchase_cost_company": purchase_cost,
                "landed_cost_unit_amount": landed_cost,
                "original_total_cost": purchase_cost + landed_cost,
                "last_revaluation_date": "2026-08-15",
                "last_revaluation_rate": 4000.0,
                "last_revalued_cost": purchase_cost + landed_cost,
                "last_sale_price": sale_price,
                "previous_exchange_rate_value": 4000.0,
                "current_exchange_rate_value": 4000.0,
                "previous_converted_purchase_cost": purchase_cost,
                "current_converted_purchase_cost": purchase_cost,
                "landed_unit_cost": purchase_cost + landed_cost,
                "converted_purchase_price": purchase_cost + landed_cost,
                "old_sale_price": 0.0,
                "markup_type": "percentage",
                "markup_value": 20.0,
                "calculated_sale_price": sale_price,
                "approved_sale_price": sale_price,
                "rule_line_id": rule_two.line_ids.id,
                "effective_date": "2026-08-15",
                "conversion_date": "2026-08-15",
                "approved_by": self.env.user.id,
                "approved_date": fields.Datetime.now(),
                "state": "approved",
                "cost_source": "landed_cost",
            }
        )

        self._create_company_rate(usd, "2026-08-16", 5000.0)

        company_two_revaluation = self.env["sale.price.update"].search(
            [
                ("company_id", "=", company_two.id),
                ("product_id", "=", product_two.id),
                ("cost_source", "=", "currency_revaluation"),
            ]
        )
        self.assertFalse(company_two_revaluation)
        self.assertAlmostEqual(product_two.product_tmpl_id.list_price, 6000.0)

        self.env["res.currency.rate"].create(
            {
                "name": "2026-08-16",
                "currency_id": usd.id,
                "company_id": company_two.id,
                "rate": 1.0 / 5000.0,
            }
        )

        company_two_revaluation = self.env["sale.price.update"].search(
            [
                ("company_id", "=", company_two.id),
                ("product_id", "=", product_two.id),
                ("cost_source", "=", "currency_revaluation"),
            ]
        )
        self.assertEqual(len(company_two_revaluation), 1)
        self.assertAlmostEqual(product_two.product_tmpl_id.list_price, 7200.0)

