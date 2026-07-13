from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import SavepointCase, tagged


@tagged("post_install", "-at_install")
class TestPurchaseSalePriceApproval(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.user_group = cls.env.ref("purchase_sale_price_approval.group_sale_price_user")
        cls.manager_group = cls.env.ref("purchase_sale_price_approval.group_sale_price_manager")
        cls.admin_group = cls.env.ref("purchase_sale_price_approval.group_sale_price_admin")
        cls.purchase_group = cls.env.ref("purchase.group_purchase_user")
        cls.purchase_manager_group = cls.env.ref("purchase.group_purchase_manager")

        cls.env["ir.config_parameter"].sudo().set_param(
            "purchase_sale_price_approval.enable_sale_price_approval", True
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "purchase_sale_price_approval.include_service_products", False
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "purchase_sale_price_approval.allow_manual_approved_price", True
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "purchase_sale_price_approval.block_price_decrease", False
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "purchase_sale_price_approval.sale_price_rounding", 0
        )

        cls.manager_user = cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Sale Price Manager",
                "login": "sale_price_manager",
                "email": "sale_price_manager@example.com",
                "groups_id": [
                    Command.link(cls.purchase_group.id),
                    Command.link(cls.purchase_manager_group.id),
                    Command.link(cls.manager_group.id),
                ],
                "company_id": cls.company.id,
                "company_ids": [Command.set(cls.company.ids)],
            }
        )
        cls.normal_user = cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Sale Price User",
                "login": "sale_price_user",
                "email": "sale_price_user@example.com",
                "groups_id": [
                    Command.link(cls.purchase_group.id),
                    Command.link(cls.user_group.id),
                ],
                "company_id": cls.company.id,
                "company_ids": [Command.set(cls.company.ids)],
            }
        )

        cls.vendor = cls.env["res.partner"].create({"name": "Vendor A", "supplier_rank": 1})
        cls.parent_category = cls.env["product.category"].create({"name": "Electronics"})
        cls.child_category = cls.env["product.category"].create(
            {"name": "Laptops", "parent_id": cls.parent_category.id}
        )
        cls.other_category = cls.env["product.category"].create({"name": "Office"})
        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.currency_mmk = cls.company.currency_id
        cls.currency_usd = cls.env.ref("base.USD")
        cls.env["res.currency.rate"].create(
            {
                "name": fields.Date.today(),
                "currency_id": cls.currency_usd.id,
                "rate": 0.000476,
                "company_id": cls.company.id,
            }
        )

        cls.product_a = cls.env["product.product"].create(
            {
                "name": "Laptop A",
                "type": "consu",
                "categ_id": cls.child_category.id,
                "uom_id": cls.uom_unit.id,
                "uom_po_id": cls.uom_unit.id,
                "list_price": 1000000,
                "standard_price": 900000,
            }
        )
        cls.product_b = cls.env["product.product"].create(
            {
                "name": "Office Product",
                "type": "consu",
                "categ_id": cls.other_category.id,
                "uom_id": cls.uom_unit.id,
                "uom_po_id": cls.uom_unit.id,
                "list_price": 500000,
                "standard_price": 450000,
            }
        )
        cls.service_product = cls.env["product.product"].create(
            {
                "name": "Installation Service",
                "type": "service",
                "categ_id": cls.other_category.id,
                "uom_id": cls.uom_unit.id,
                "uom_po_id": cls.uom_unit.id,
                "list_price": 10000,
            }
        )

        cls.rule = cls.env["sale.price.rule"].create(
            {
                "name": "Default Rules",
                "company_id": cls.company.id,
                "currency_id": cls.currency_mmk.id,
            }
        )
        cls.product_line = cls.env["sale.price.rule.line"].create(
            {
                "rule_id": cls.rule.id,
                "apply_on": "product",
                "product_id": cls.product_a.id,
                "from_amount": 1000000,
                "to_amount": 2000000,
                "markup_type": "percentage",
                "markup_value": 10.0,
                "valid_from": fields.Date.today(),
            }
        )
        cls.category_line = cls.env["sale.price.rule.line"].create(
            {
                "rule_id": cls.rule.id,
                "apply_on": "category",
                "categ_id": cls.parent_category.id,
                "from_amount": 500000,
                "to_amount": 3000000,
                "markup_type": "fixed",
                "markup_value": 100000.0,
                "priority": 20,
                "valid_from": fields.Date.today(),
            }
        )
        cls.all_product_line = cls.env["sale.price.rule.line"].create(
            {
                "rule_id": cls.rule.id,
                "apply_on": "all",
                "from_amount": 0,
                "to_amount": 0,
                "markup_type": "percentage",
                "markup_value": 5.0,
                "priority": 50,
                "valid_from": fields.Date.today(),
            }
        )
        cls.rule.action_activate()

    def _create_purchase_order(self, product, unit_price, qty=1.0, currency=None):
        currency = currency or self.currency_mmk
        return self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "company_id": self.company.id,
                "currency_id": currency.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "name": product.display_name,
                            "product_qty": qty,
                            "product_uom": product.uom_po_id.id,
                            "price_unit": unit_price,
                            "date_planned": fields.Datetime.now(),
                        }
                    )
                ],
            }
        )

    def test_percentage_markup_calculation(self):
        update_model = self.env["sale.price.update"]
        price = update_model._calculate_sale_price(1500000, "percentage", 10.0, self.currency_mmk)
        self.assertEqual(price, 1650000)

    def test_fixed_markup_calculation(self):
        update_model = self.env["sale.price.update"]
        price = update_model._calculate_sale_price(1500000, "fixed", 100000.0, self.currency_mmk)
        self.assertEqual(price, 1600000)

    def test_rule_priority_product_over_category(self):
        line = self.env["sale.price.rule.line"]._find_matching_rule_line(
            self.product_a,
            1500000,
            self.company,
            self.currency_mmk,
            fields.Date.today(),
        )
        self.assertEqual(line, self.product_line)

    def test_category_rule_fallback_and_parent_category_matching(self):
        line = self.env["sale.price.rule.line"]._find_matching_rule_line(
            self.product_b,
            700000,
            self.company,
            self.currency_mmk,
            fields.Date.today(),
        )
        self.assertEqual(line, self.all_product_line)

        temp_product = self.env["product.product"].create(
            {
                "name": "Laptop B",
                "type": "consu",
                "categ_id": self.child_category.id,
                "uom_id": self.uom_unit.id,
                "uom_po_id": self.uom_unit.id,
                "list_price": 1200000,
            }
        )
        line = self.env["sale.price.rule.line"]._find_matching_rule_line(
            temp_product,
            700000,
            self.company,
            self.currency_mmk,
            fields.Date.today(),
        )
        self.assertEqual(line, self.category_line)

    def test_valid_date_range_selection(self):
        future_line = self.env["sale.price.rule.line"].create(
            {
                "rule_id": self.rule.id,
                "apply_on": "all",
                "from_amount": 1000000,
                "to_amount": 2000000,
                "markup_type": "percentage",
                "markup_value": 99.0,
                "priority": 1,
                "valid_from": fields.Date.today() + timedelta(days=30),
            }
        )
        line = self.env["sale.price.rule.line"]._find_matching_rule_line(
            self.product_b,
            1500000,
            self.company,
            self.currency_mmk,
            fields.Date.today(),
        )
        self.assertNotEqual(line, future_line)

    def test_currency_conversion_matching(self):
        line = self.env["sale.price.rule.line"]._find_matching_rule_line(
            self.product_a,
            715.0,
            self.company,
            self.currency_usd,
            fields.Date.today(),
        )
        self.assertEqual(line, self.product_line)

    def test_no_rule_found_behavior(self):
        self.rule.action_archive()
        line = self.env["sale.price.rule.line"]._find_matching_rule_line(
            self.product_a,
            1500000,
            self.company,
            self.currency_mmk,
            fields.Date.today(),
        )
        self.assertFalse(line)
        self.rule.action_set_to_draft()
        self.rule.action_activate()

    def test_po_confirmation_creates_pending_update_without_modifying_list_price(self):
        order = self._create_purchase_order(self.product_a, 1500000, qty=10)
        old_price = self.product_a.product_tmpl_id.with_company(self.company).list_price
        order.button_confirm()
        self.assertEqual(len(order.sale_price_update_ids), 1)
        update = order.sale_price_update_ids[0]
        self.assertEqual(update.state, "pending")
        self.assertEqual(update.purchase_price, 1500000)
        self.assertEqual(update.calculated_sale_price, 1650000)
        self.assertEqual(self.product_a.product_tmpl_id.with_company(self.company).list_price, old_price)

    def test_manager_approval_updates_list_price(self):
        order = self._create_purchase_order(self.product_a, 1500000)
        order.button_confirm()
        update = order.sale_price_update_ids[0]
        update.with_user(self.manager_user).action_approve()
        self.assertEqual(update.state, "approved")
        self.assertEqual(self.product_a.product_tmpl_id.with_company(self.company).list_price, 1650000)
        self.assertTrue(self.env["sale.price.history"].search([("sale_price_update_id", "=", update.id)]))

    def test_normal_user_cannot_approve(self):
        order = self._create_purchase_order(self.product_a, 1500000)
        order.button_confirm()
        update = order.sale_price_update_ids[0]
        with self.assertRaises(AccessError):
            update.with_user(self.normal_user).action_approve()

    def test_rejection_does_not_update_list_price(self):
        order = self._create_purchase_order(self.product_a, 1500000)
        order.button_confirm()
        update = order.sale_price_update_ids[0]
        update.rejection_reason = "Margin not approved"
        update.with_user(self.manager_user).action_reject()
        self.assertEqual(update.state, "rejected")
        self.assertEqual(self.product_a.product_tmpl_id.with_company(self.company).list_price, 1000000)

    def test_duplicate_confirmation_does_not_create_duplicates(self):
        order = self._create_purchase_order(self.product_a, 1500000)
        order.button_confirm()
        order._generate_pending_sale_price_updates()
        self.assertEqual(len(order.sale_price_update_ids), 1)

    def test_po_cancellation_cancels_pending_updates(self):
        order = self._create_purchase_order(self.product_a, 1500000)
        order.button_confirm()
        update = order.sale_price_update_ids[0]
        order.button_cancel()
        self.assertEqual(update.state, "cancelled")

    def test_po_cancellation_does_not_revert_approved_prices(self):
        order = self._create_purchase_order(self.product_a, 1500000)
        order.button_confirm()
        update = order.sale_price_update_ids[0]
        update.with_user(self.manager_user).action_approve()
        order.button_cancel()
        self.assertEqual(update.state, "approved")
        self.assertEqual(self.product_a.product_tmpl_id.with_company(self.company).list_price, 1650000)

    def test_overlapping_rule_validation(self):
        with self.assertRaises(ValidationError):
            self.env["sale.price.rule.line"].create(
                {
                    "rule_id": self.rule.id,
                    "apply_on": "product",
                    "product_id": self.product_a.id,
                    "from_amount": 1500000,
                    "to_amount": 2500000,
                    "markup_type": "percentage",
                    "markup_value": 15.0,
                    "valid_from": fields.Date.today(),
                }
            )

    def test_batch_approval(self):
        first_order = self._create_purchase_order(self.product_a, 1500000)
        second_order = self._create_purchase_order(self.product_b, 600000)
        first_order.button_confirm()
        second_order.button_confirm()
        wizard = self.env["batch.sale.price.approval.wizard"].create(
            {
                "action_type": "approve",
                "update_ids": [
                    Command.set((first_order.sale_price_update_ids | second_order.sale_price_update_ids).ids)
                ],
            }
        )
        wizard.with_user(self.manager_user).action_process()
        self.assertEqual(first_order.sale_price_update_ids.state, "approved")
        self.assertEqual(second_order.sale_price_update_ids.state, "approved")

    def test_block_price_decrease_setting(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "purchase_sale_price_approval.block_price_decrease", True
        )
        order = self._create_purchase_order(self.product_a, 1500000)
        order.button_confirm()
        update = order.sale_price_update_ids[0]
        update.approved_sale_price = 900000
        with self.assertRaises(ValidationError):
            update.with_user(self.manager_user).action_approve()
        self.env["ir.config_parameter"].sudo().set_param(
            "purchase_sale_price_approval.block_price_decrease", False
        )

    def test_manual_approved_price_setting(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "purchase_sale_price_approval.allow_manual_approved_price", False
        )
        order = self._create_purchase_order(self.product_a, 1500000)
        order.button_confirm()
        update = order.sale_price_update_ids[0]
        update.approved_sale_price = 1700000
        with self.assertRaises(ValidationError):
            update.with_user(self.manager_user).action_approve()
        self.env["ir.config_parameter"].sudo().set_param(
            "purchase_sale_price_approval.allow_manual_approved_price", True
        )

    def test_service_product_inclusion_setting(self):
        order = self._create_purchase_order(self.service_product, 50000)
        order.button_confirm()
        self.assertFalse(order.sale_price_update_ids)
        self.env["ir.config_parameter"].sudo().set_param(
            "purchase_sale_price_approval.include_service_products", True
        )
        order = self._create_purchase_order(self.service_product, 50000)
        order.button_confirm()
        self.assertTrue(order.sale_price_update_ids)
        self.env["ir.config_parameter"].sudo().set_param(
            "purchase_sale_price_approval.include_service_products", False
        )

    def test_sale_price_rounding(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "purchase_sale_price_approval.sale_price_rounding", 1000
        )
        update_model = self.env["sale.price.update"]
        price = update_model._calculate_sale_price(1653250, "fixed", 0.0, self.currency_mmk)
        self.assertEqual(price, 1653000)
        self.env["ir.config_parameter"].sudo().set_param(
            "purchase_sale_price_approval.sale_price_rounding", 0
        )
