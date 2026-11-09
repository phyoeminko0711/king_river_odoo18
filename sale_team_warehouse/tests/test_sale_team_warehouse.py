from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSaleTeamWarehouse(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "Warehouse Customer"})
        cls.product = cls.env["product.product"].create(
            {
                "name": "Warehouse Test Product",
                "type": "consu",
                "list_price": 100.0,
            }
        )
        cls.warehouse_yangon = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)],
            limit=1,
        )
        if not cls.warehouse_yangon:
            cls.warehouse_yangon = cls.env["stock.warehouse"].create(
                {
                    "name": "Yangon Warehouse",
                    "code": "YGN",
                    "company_id": cls.company.id,
                }
            )
        cls.warehouse_mandalay = cls.env["stock.warehouse"].create(
            {
                "name": "Mandalay Warehouse",
                "code": "MDY",
                "company_id": cls.company.id,
            }
        )
        cls.team_yangon = cls.env["crm.team"].create(
            {
                "name": "Yangon Sales Team",
                "company_id": cls.company.id,
                "warehouse_id": cls.warehouse_yangon.id,
            }
        )
        cls.team_mandalay = cls.env["crm.team"].create(
            {
                "name": "Mandalay Sales Team",
                "company_id": cls.company.id,
                "warehouse_id": cls.warehouse_mandalay.id,
            }
        )
        cls.team_without_warehouse = cls.env["crm.team"].create(
            {
                "name": "No Warehouse Sales Team",
                "company_id": cls.company.id,
            }
        )

    def _order_vals(self, team=None, warehouse=None):
        vals = {
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "order_line": [
                Command.create(
                    {
                        "product_id": self.product.id,
                        "product_uom_qty": 1.0,
                        "price_unit": 100.0,
                    }
                )
            ],
        }
        if team:
            vals["team_id"] = team.id
        if warehouse:
            vals["warehouse_id"] = warehouse.id
        return vals

    def test_create_sets_warehouse_from_team(self):
        order = self.env["sale.order"].create(self._order_vals(team=self.team_yangon))
        self.assertEqual(order.warehouse_id, self.warehouse_yangon)

    def test_explicit_warehouse_is_preserved(self):
        order = self.env["sale.order"].create(
            self._order_vals(team=self.team_yangon, warehouse=self.warehouse_mandalay)
        )
        self.assertEqual(order.warehouse_id, self.warehouse_mandalay)

    def test_change_team_updates_warehouse(self):
        order = self.env["sale.order"].create(self._order_vals(team=self.team_yangon))
        order.write({"team_id": self.team_mandalay.id})
        self.assertEqual(order.warehouse_id, self.warehouse_mandalay)

    def test_team_without_warehouse_keeps_existing_warehouse(self):
        order = self.env["sale.order"].create(self._order_vals(team=self.team_yangon))
        order.write({"team_id": self.team_without_warehouse.id})
        self.assertEqual(order.warehouse_id, self.warehouse_yangon)

    def test_confirmation_uses_selected_warehouse(self):
        order = self.env["sale.order"].create(self._order_vals(team=self.team_mandalay))
        order.action_confirm()
        self.assertTrue(order.picking_ids)
        self.assertTrue(all(picking.picking_type_id.warehouse_id == self.warehouse_mandalay for picking in order.picking_ids))

    def test_stocked_products_use_only_the_order_warehouse(self):
        product = self.env["product.product"].create(
            {"name": "Warehouse Only Product", "type": "consu", "is_storable": True}
        )
        self.env["stock.quant"]._update_available_quantity(
            product, self.warehouse_yangon.lot_stock_id, 5.0
        )
        vals = self._order_vals(team=self.team_yangon)
        vals["order_line"] = [
            Command.create({"product_id": product.id, "product_uom_qty": 3.0})
        ]
        order = self.env["sale.order"].create(vals)
        self.assertIn(product, order.available_sale_product_ids)
        self.assertIn(product.product_tmpl_id, order.available_sale_template_ids)
        other_order = self.env["sale.order"].create(
            {"partner_id": self.partner.id, "team_id": self.team_mandalay.id}
        )
        self.assertNotIn(product, other_order.available_sale_product_ids)
        self.assertNotIn(product.product_tmpl_id, other_order.available_sale_template_ids)
        self.assertTrue(
            any(
                clause[0:2] == ("id", "in") and product.id in clause[2]
                for clause in order._get_product_catalog_domain()
                if isinstance(clause, tuple)
            )
        )

        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            order.order_line.write({"product_uom_qty": 6.0})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            order.write({"team_id": self.team_mandalay.id})

        other_vals = self._order_vals(team=self.team_mandalay)
        other_vals["order_line"] = [
            Command.create({"product_id": product.id, "product_uom_qty": 1.0})
        ]
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["sale.order"].create(other_vals)

        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            order.write({"order_line": [Command.create({"product_id": product.id, "product_uom_qty": 3.0})]})

        self.env["stock.quant"]._update_available_quantity(
            product, self.warehouse_yangon.lot_stock_id, -5.0
        )
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            order.action_confirm()

    def test_line_pricelist_changes_only_selected_line(self):
        base_pricelist = self.env["product.pricelist"].create(
            {"name": "Base Test Prices", "currency_id": self.company.currency_id.id}
        )
        alternate_pricelist = self.env["product.pricelist"].create(
            {
                "name": "Alternate Test Prices",
                "currency_id": self.company.currency_id.id,
                "item_ids": [Command.create({"applied_on": "3_global", "compute_price": "fixed", "fixed_price": 150.0})],
            }
        )
        vals = self._order_vals()
        vals["pricelist_id"] = base_pricelist.id
        vals["order_line"].append(
            Command.create(
                {"product_id": self.product.id, "product_uom_qty": 1.0, "price_unit": 100.0}
            )
        )
        order = self.env["sale.order"].create(vals)
        first, second = order.order_line.sorted("id")
        self.assertEqual(first.pricelist_type_id, base_pricelist)
        self.assertEqual(second.pricelist_type_id, base_pricelist)

        draft_line = self.env["sale.order.line"].new(
            {
                "order_id": order.id,
                "product_id": self.product.id,
                "product_uom_qty": 1.0,
            }
        )
        draft_line.pricelist_type_id = alternate_pricelist
        draft_line._onchange_pricelist_type_id()
        self.assertEqual(draft_line.price_unit, 150.0)

        first.write({"pricelist_type_id": alternate_pricelist.id})
        self.assertEqual(first.pricelist_type_id, alternate_pricelist)
        self.assertEqual(first.price_unit, 150.0)
        self.assertEqual(second.price_unit, 100.0)
        self.assertEqual(second.pricelist_type_id, base_pricelist)
        self.assertEqual(order.pricelist_id, base_pricelist)

        replacement_pricelist = self.env["product.pricelist"].create(
            {"name": "Replacement Test Prices", "currency_id": self.company.currency_id.id}
        )
        order.write({"pricelist_id": replacement_pricelist.id})
        self.assertEqual(first.pricelist_type_id, alternate_pricelist)
        self.assertEqual(second.pricelist_type_id, replacement_pricelist)

        salesperson = self.env["res.users"].create(
            {
                "name": "Pricelist Test Salesperson",
                "login": "pricelist_test_salesperson",
                "groups_id": [Command.set([self.env.ref("base.group_user").id, self.env.ref("sales_team.group_sale_salesman").id])],
            }
        )
        with self.assertRaises(AccessError):
            first.with_user(salesperson).write({"pricelist_type_id": base_pricelist.id})

        other_currency = self.env["res.currency"].search(
            [("id", "!=", self.company.currency_id.id)], limit=1
        )
        foreign_pricelist = self.env["product.pricelist"].create(
            {"name": "Foreign Test Prices", "currency_id": other_currency.id}
        )
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            first.write({"pricelist_type_id": foreign_pricelist.id})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            order.write({"pricelist_id": foreign_pricelist.id})
