from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import float_compare


class RepairOrder(models.Model):
    _inherit = "repair.order"

    invoice_ids = fields.One2many(
        "account.move",
        "repair_order_id",
        string="Customer Invoices",
    )
    invoice_count = fields.Integer(
        string="Invoice Count",
        compute="_compute_invoice_count",
    )

    @api.depends("invoice_ids.state", "invoice_ids.move_type")
    def _compute_invoice_count(self):
        for repair in self:
            repair.invoice_count = len(
                repair.invoice_ids.filtered(
                    lambda move: move.move_type == "out_invoice" and move.state != "cancel"
                )
            )

    def _get_active_customer_invoices(self):
        return self.invoice_ids.filtered(
            lambda move: move.move_type == "out_invoice" and move.state != "cancel"
        )

    def _get_invoiceable_repair_moves(self):
        self.ensure_one()
        invoiced_move_ids = self.env["account.move.line"].search(
            [
                ("repair_move_id", "in", self.move_ids.ids),
                ("move_id.move_type", "=", "out_invoice"),
                ("move_id.state", "!=", "cancel"),
            ]
        ).repair_move_id.ids
        return self.move_ids.filtered(
            lambda move: move.repair_line_type == "add"
            and move.product_id
            and move.state != "cancel"
            and move.id not in invoiced_move_ids
            and float_compare(
                move.product_uom_qty,
                0.0,
                precision_rounding=move.product_uom.rounding,
            )
            > 0
        )

    def _get_invoiceable_repair_charge_lines(self):
        self.ensure_one()
        invoiced_charge_line_ids = self.env["account.move.line"].search(
            [
                ("repair_charge_line_id", "in", self.repair_charge_line_ids.ids),
                ("move_id.move_type", "=", "out_invoice"),
                ("move_id.state", "!=", "cancel"),
            ]
        ).repair_charge_line_id.ids
        return self.repair_charge_line_ids.filtered(
            lambda line: line.product_id
            and line.id not in invoiced_charge_line_ids
            and float_compare(
                line.product_uom_qty,
                0.0,
                precision_rounding=line.product_uom_id.rounding,
            )
            > 0
        )

    def _prepare_product_invoice_line_vals(
        self, product, quantity, uom, price_unit, fiscal_position, extra_vals=None
    ):
        self.ensure_one()
        product = product.with_company(self.company_id)
        accounts = product.product_tmpl_id.get_product_accounts(fiscal_pos=fiscal_position)
        income_account = accounts.get("income")
        if not income_account:
            raise ValidationError(
                _("Please configure an income account for product %s.")
                % product.display_name
            )
        taxes = product.taxes_id._filter_taxes_by_company(self.company_id)
        if fiscal_position:
            taxes = fiscal_position.map_tax(taxes)
        name = product.get_product_multiline_description_sale() or product.display_name
        vals = {
            "product_id": product.id,
            "name": name,
            "quantity": quantity,
            "product_uom_id": uom.id,
            "price_unit": price_unit,
            "tax_ids": [(6, 0, taxes.ids)],
            "account_id": income_account.id,
        }
        if extra_vals:
            vals.update(extra_vals)
        return vals

    def _prepare_repair_invoice_line_vals(self, move, fiscal_position):
        vals = self._prepare_product_invoice_line_vals(
            move.product_id,
            move.product_uom_qty,
            move.product_uom,
            move.price_unit,
            fiscal_position,
            {"repair_move_id": move.id},
        )
        if move.name:
            vals["name"] = vals["name"] or move.name
        return vals

    def _prepare_repair_charge_invoice_line_vals(self, charge_line, fiscal_position):
        return self._prepare_product_invoice_line_vals(
            charge_line.product_id,
            charge_line.product_uom_qty,
            charge_line.product_uom_id,
            charge_line.price_unit,
            fiscal_position,
            {
                "repair_charge_line_id": charge_line.id,
            },
        )

    def _prepare_repair_invoice_vals(self, repair_moves, repair_charge_lines=None):
        self.ensure_one()
        repair_charge_lines = repair_charge_lines or self.env["workshop.repair.charge.line"]
        fiscal_position = self.env["account.fiscal.position"].with_company(
            self.company_id
        )._get_fiscal_position(self.partner_id)
        invoice_lines = [
            (0, 0, self._prepare_repair_invoice_line_vals(move, fiscal_position))
            for move in repair_moves
        ]
        invoice_lines.extend(
            [
                (0, 0, self._prepare_repair_charge_invoice_line_vals(line, fiscal_position))
                for line in repair_charge_lines
            ]
        )
        return {
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "invoice_date": fields.Date.context_today(self),
            "invoice_origin": self.display_name,
            "repair_order_id": self.id,
            "company_id": self.company_id.id,
            "currency_id": self.company_id.currency_id.id,
            "fiscal_position_id": fiscal_position.id,
            "invoice_line_ids": invoice_lines,
        }

    def _validate_repair_invoice_creation(self):
        self.ensure_one()
        if not self.env.user.has_group("account.group_account_invoice"):
            raise AccessError(_("You do not have permission to create customer invoices."))
        if self.state != "done":
            raise ValidationError(_("Complete the Repair Order before creating an invoice."))
        if not self.delivery_inspection_completed:
            raise ValidationError(_("Complete the Delivery Check before creating an invoice."))
        if not self.partner_id:
            raise ValidationError(_("Select a customer before creating an invoice."))
        if not self.company_id:
            raise ValidationError(_("A company is required before creating an invoice."))
        if self._get_active_customer_invoices():
            raise ValidationError(_("A Customer Invoice already exists for this Repair Order."))
        repair_moves = self._get_invoiceable_repair_moves()
        repair_charge_lines = self._get_invoiceable_repair_charge_lines()
        if not repair_moves and not repair_charge_lines:
            raise ValidationError(_("There are no invoiceable Repair lines."))
        return repair_moves, repair_charge_lines

    def action_create_invoice(self):
        self.ensure_one()
        existing_invoice = self._get_active_customer_invoices()[:1]
        if existing_invoice:
            return existing_invoice._get_records_action()
        repair_moves, repair_charge_lines = self._validate_repair_invoice_creation()
        invoice = self.env["account.move"].create(
            self._prepare_repair_invoice_vals(repair_moves, repair_charge_lines)
        )
        self.message_post(
            body=_(
                "Draft Customer Invoice <a href='#' data-oe-model='account.move' data-oe-id='%(invoice_id)s'>%(invoice_name)s</a> created.",
                invoice_id=invoice.id,
                invoice_name=invoice.display_name,
            )
        )
        return invoice._get_records_action()

    def action_view_invoices(self):
        self.ensure_one()
        invoices = self.invoice_ids.filtered(lambda move: move.move_type == "out_invoice")
        if len(invoices) == 1:
            return invoices._get_records_action()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "account.action_move_out_invoice_type"
        )
        action["domain"] = [("id", "in", invoices.ids)]
        action["context"] = {
            **self.env.context,
            "default_move_type": "out_invoice",
            "create": False,
        }
        return action
