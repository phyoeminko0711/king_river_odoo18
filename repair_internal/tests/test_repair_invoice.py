from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestRepairInternalInvoice(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "Repair Invoice Customer"})
        cls.income_account = cls.env["account.account"].search(
            [
                ("company_ids", "in", cls.company.ids),
                ("account_type", "=", "income"),
                ("deprecated", "=", False),
            ],
            limit=1,
        )
        if not cls.income_account:
            cls.income_account = cls.env["account.account"].create(
                {
                    "name": "Repair Test Income",
                    "code": "XRTI",
                    "account_type": "income",
                    "company_ids": [Command.link(cls.company.id)],
                }
            )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Repair Invoice Part",
                "type": "consu",
                "list_price": 100.0,
                "property_account_income_id": cls.income_account.id,
            }
        )
        cls.service = cls.env["product.product"].create(
            {
                "name": "Repair Invoice Service",
                "type": "service",
                "list_price": 50.0,
                "property_account_income_id": cls.income_account.id,
            }
        )

    def _create_done_repair(self, delivery_done=True):
        repair = self.env["repair.order"].create(
            {
                "partner_id": self.partner.id,
                "schedule_date": fields.Datetime.now(),
            }
        )
        self.env["stock.move"].create(
            [
                {
                    "repair_id": repair.id,
                    "repair_line_type": "add",
                    "product_id": self.product.id,
                    "product_uom_qty": 2.0,
                    "product_uom": self.product.uom_id.id,
                    "price_unit": 100.0,
                    "location_id": repair.location_id.id,
                    "location_dest_id": repair.location_dest_id.id,
                    "company_id": repair.company_id.id,
                },
                {
                    "repair_id": repair.id,
                    "repair_line_type": "add",
                    "product_id": self.service.id,
                    "product_uom_qty": 1.0,
                    "product_uom": self.service.uom_id.id,
                    "price_unit": 50.0,
                    "location_id": repair.location_id.id,
                    "location_dest_id": repair.location_dest_id.id,
                    "company_id": repair.company_id.id,
                },
                {
                    "repair_id": repair.id,
                    "repair_line_type": "remove",
                    "product_id": self.product.id,
                    "product_uom_qty": 1.0,
                    "product_uom": self.product.uom_id.id,
                    "price_unit": 25.0,
                    "location_id": repair.location_dest_id.id,
                    "location_dest_id": repair.parts_location_id.id,
                    "company_id": repair.company_id.id,
                },
            ]
        )
        repair.state = "done"
        if delivery_done:
            repair.delivery_inspection_completed = True
        return repair

    def test_incomplete_repair_order_cannot_create_invoice(self):
        repair = self.env["repair.order"].create({"partner_id": self.partner.id})
        with self.assertRaisesRegex(ValidationError, "Complete the Repair Order"):
            repair.action_create_invoice()

    def test_delivery_check_incomplete_blocks_invoice_creation(self):
        repair = self._create_done_repair(delivery_done=False)
        with self.assertRaisesRegex(ValidationError, "Complete the Delivery Check"):
            repair.action_create_invoice()

    def test_completed_repair_creates_draft_invoice(self):
        repair = self._create_done_repair()
        action = repair.action_create_invoice()
        invoice = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(invoice.move_type, "out_invoice")
        self.assertEqual(invoice.partner_id, self.partner)
        self.assertEqual(invoice.repair_order_id, repair)
        self.assertEqual(len(invoice.invoice_line_ids), 2)
        self.assertEqual(set(invoice.invoice_line_ids.mapped("repair_move_id")), set(repair.move_ids.filtered(lambda move: move.repair_line_type == "add")))

    def test_create_invoice_twice_opens_existing_invoice(self):
        repair = self._create_done_repair()
        first_action = repair.action_create_invoice()
        second_action = repair.action_create_invoice()
        self.assertEqual(first_action["res_id"], second_action["res_id"])
        self.assertEqual(repair.invoice_count, 1)

    def test_cancelled_invoice_allows_replacement(self):
        repair = self._create_done_repair()
        first_invoice = self.env["account.move"].browse(repair.action_create_invoice()["res_id"])
        first_invoice.button_cancel()
        second_invoice = self.env["account.move"].browse(repair.action_create_invoice()["res_id"])
        self.assertNotEqual(first_invoice, second_invoice)

    def test_invoice_smart_button_opens_invoice(self):
        repair = self._create_done_repair()
        invoice = self.env["account.move"].browse(repair.action_create_invoice()["res_id"])
        action = repair.action_view_invoices()
        self.assertEqual(action["res_id"], invoice.id)

    def test_user_without_invoice_permission_cannot_create_invoice(self):
        user = self.env["res.users"].create(
            {
                "name": "No Invoice User",
                "login": "no_invoice_user",
                "groups_id": [Command.set([self.env.ref("base.group_user").id])],
            }
        )
        repair = self._create_done_repair()
        with self.assertRaises(AccessError):
            repair.with_user(user).action_create_invoice()
