from odoo import Command
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
