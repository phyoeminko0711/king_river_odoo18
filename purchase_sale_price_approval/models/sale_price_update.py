from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_round


class SalePriceUpdate(models.Model):
    _name = "sale.price.update"
    _description = "Sale Price Update"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "requested_date desc, id desc"
    _rec_name = "name"
    _check_company_auto = True

    name = fields.Char(required=True, readonly=True, copy=False, default="New")
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one("res.currency", required=True)
    purchase_order_id = fields.Many2one("purchase.order", required=True, ondelete="restrict", index=True)
    purchase_order_line_id = fields.Many2one(
        "purchase.order.line",
        required=True,
        ondelete="restrict",
        index=True,
    )
    vendor_id = fields.Many2one(related="purchase_order_id.partner_id", store=True, index=True)
    product_id = fields.Many2one("product.product", required=True, index=True)
    product_tmpl_id = fields.Many2one(
        related="product_id.product_tmpl_id",
        store=True,
        index=True,
    )
    product_category_id = fields.Many2one(
        related="product_id.categ_id",
        store=True,
    )
    purchase_quantity = fields.Float(readonly=True, string="Quantity")
    purchase_uom_id = fields.Many2one("uom.uom", readonly=True, string="Unit of Measure")
    purchase_price = fields.Monetary(required=True, readonly=True, currency_field="source_currency_id", string="Purchase Price")
    source_currency_id = fields.Many2one("res.currency", readonly=True)
    converted_purchase_price = fields.Monetary(readonly=True, currency_field="currency_id")
    old_sale_price = fields.Monetary(required=True, readonly=True, currency_field="currency_id", string="Previous Sale Price")
    markup_type = fields.Selection([("percentage", "Percentage"), ("fixed", "Fixed Amount")], readonly=True)
    markup_value = fields.Float(readonly=True)
    calculated_sale_price = fields.Monetary(required=True, readonly=True, currency_field="currency_id", string="Proposed Sale Price")
    approved_sale_price = fields.Monetary(currency_field="currency_id", string="Approved Sale Price")
    rule_line_id = fields.Many2one("sale.price.rule.line", readonly=True)
    effective_date = fields.Date(required=True, readonly=True, string="Effective Date")
    conversion_date = fields.Date(readonly=True)
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
            ("superseded", "Superseded"),
        ],
        default="pending",
        required=True,
        tracking=True,
        index=True,
    )
    requested_by = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    requested_date = fields.Datetime(default=fields.Datetime.now, readonly=True)
    approved_by = fields.Many2one("res.users", readonly=True)
    approved_date = fields.Datetime(readonly=True)
    rejected_by = fields.Many2one("res.users", readonly=True)
    rejected_date = fields.Datetime(readonly=True)
    rejection_reason = fields.Text()
    note = fields.Text()
    current_product_sale_price = fields.Monetary(
        compute="_compute_current_product_sale_price",
        currency_field="currency_id",
    )
    price_difference = fields.Monetary(
        compute="_compute_price_metrics",
        currency_field="currency_id",
    )
    price_difference_percentage = fields.Float(compute="_compute_price_metrics")
    previous_update_id = fields.Many2one("sale.price.update", readonly=True, ondelete="restrict")
    superseded_by_id = fields.Many2one("sale.price.update", readonly=True, ondelete="restrict")

    _sql_constraints = [
        ("name_company_unique", "unique(name, company_id)", "The reference must be unique per company."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = sequence.next_by_code("sale.price.update") or "New"
            if not vals.get("approved_sale_price") and vals.get("calculated_sale_price"):
                vals["approved_sale_price"] = vals["calculated_sale_price"]
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get("skip_sale_price_update_protection") or self.env.su:
            return super().write(vals)

        chatter_only_fields = {
            "message_follower_ids",
            "message_partner_ids",
            "activity_ids",
            "activity_exception_decoration",
            "activity_exception_icon",
            "activity_state",
            "activity_type_icon",
            "activity_type_id",
            "activity_user_id",
            "activity_date_deadline",
        }
        if set(vals).issubset(chatter_only_fields):
            return super().write(vals)

        terminal_records = self.filtered(lambda record: record.state in ("approved", "rejected", "cancelled", "superseded"))
        if terminal_records:
            raise ValidationError(_("Approved sale price updates cannot be modified."))

        allowed_pending_fields = {
            "approved_sale_price",
            "rejection_reason",
            "note",
        }
        if not set(vals).issubset(allowed_pending_fields):
            raise ValidationError(_("Only editable approval fields can be changed on pending sale price updates."))
        if not self.env.user.has_group("purchase_sale_price_approval.group_sale_price_manager"):
            raise ValidationError(_("Only authorized managers can modify pending sale price updates."))
        return super().write(vals)

    @api.depends("product_tmpl_id", "company_id")
    def _compute_current_product_sale_price(self):
        for record in self:
            company_currency = record.company_id.currency_id
            current_price_company = record.product_tmpl_id.with_company(record.company_id).list_price
            conversion_date = record.effective_date or fields.Date.context_today(record)
            record.current_product_sale_price = company_currency._convert(
                current_price_company,
                record.currency_id,
                record.company_id,
                conversion_date,
            )

    @api.depends("approved_sale_price", "old_sale_price")
    def _compute_price_metrics(self):
        for record in self:
            approved_sale_price = record.approved_sale_price or 0.0
            record.price_difference = approved_sale_price - record.old_sale_price
            if record.old_sale_price:
                record.price_difference_percentage = (
                    (approved_sale_price - record.old_sale_price) / record.old_sale_price
                ) * 100
            else:
                record.price_difference_percentage = 0.0

    @api.constrains("approved_sale_price")
    def _check_approved_sale_price(self):
        for record in self:
            if record.approved_sale_price is not False and record.approved_sale_price < 0:
                raise ValidationError(_("Approved Sale Price must be greater than or equal to zero."))

    def _check_manager_access(self):
        if not self.env.user.has_group("purchase_sale_price_approval.group_sale_price_manager"):
            raise AccessError(_("You are not allowed to approve or reject sale price updates."))

    @api.model
    def _get_setting_bool(self, key, default=False):
        value = self.env["ir.config_parameter"].sudo().get_param(key)
        if value is None:
            return default
        return str(value).lower() in ("true", "1", "yes")

    @api.model
    def _get_setting_float(self, key, default=0.0):
        value = self.env["ir.config_parameter"].sudo().get_param(key)
        return float(value or default)

    @api.model
    def _round_sale_price(self, amount, currency):
        rounding = self._get_setting_float("purchase_sale_price_approval.sale_price_rounding")
        rounded = amount
        if rounding:
            rounded = float_round(amount, precision_rounding=rounding)
        return currency.round(rounded)

    @api.model
    def _calculate_sale_price(self, purchase_price, markup_type, markup_value, currency):
        if markup_type == "percentage":
            proposed_price = purchase_price + (purchase_price * markup_value / 100.0)
        else:
            proposed_price = purchase_price + markup_value
        return self._round_sale_price(proposed_price, currency)

    def _post_approval_messages(self):
        self.ensure_one()
        self.message_post(
            body=_("Sale price approved. Product sale price updated to %s.") % self.approved_sale_price
        )
        self.purchase_order_id.message_post(
            body=_(
                "Sale Price Update %(update)s approved for product %(product)s. New sale price: %(price)s."
            )
            % {
                "update": self.display_name,
                "product": self.product_id.display_name,
                "price": self.approved_sale_price,
            }
        )
        if hasattr(self.product_tmpl_id, "message_post"):
            self.product_tmpl_id.message_post(
                body=_(
                    "Sale price updated from Purchase Order %(po)s through Sale Price Update %(update)s. "
                    "Old price: %(old)s, new price: %(new)s."
                )
                % {
                    "po": self.purchase_order_id.display_name,
                    "update": self.display_name,
                    "old": self.old_sale_price,
                    "new": self.approved_sale_price,
                }
            )

    def _create_history_record(self):
        self.ensure_one()
        self.env["sale.price.history"].create(
            {
                "name": self.name,
                "company_id": self.company_id.id,
                "product_id": self.product_id.id,
                "product_tmpl_id": self.product_tmpl_id.id,
                "product_category_id": self.product_category_id.id,
                "purchase_order_id": self.purchase_order_id.id,
                "purchase_order_line_id": self.purchase_order_line_id.id,
                "sale_price_update_id": self.id,
                "vendor_id": self.vendor_id.id,
                "rule_line_id": self.rule_line_id.id,
                "old_sale_price": self.old_sale_price,
                "purchase_price": self.converted_purchase_price,
                "markup_type": self.markup_type,
                "markup_value": self.markup_value,
                "calculated_sale_price": self.calculated_sale_price,
                "approved_sale_price": self.approved_sale_price,
                "currency_id": self.currency_id.id,
                "effective_date": self.effective_date,
                "approved_by": self.approved_by.id,
                "approved_date": self.approved_date,
            }
        )

    def _supersede_older_pending_updates(self):
        for record in self:
            older_updates = self.search(
                [
                    ("id", "!=", record.id),
                    ("company_id", "=", record.company_id.id),
                    ("product_id", "=", record.product_id.id),
                    ("state", "=", "pending"),
                    ("effective_date", "<", record.effective_date),
                ]
            )
            if older_updates:
                older_updates.with_context(skip_sale_price_update_protection=True).write(
                    {
                        "state": "superseded",
                        "superseded_by_id": record.id,
                    }
                )

    def action_approve(self):
        self._check_manager_access()
        for record in self:
            record.ensure_one()
            if record.state != "pending":
                raise UserError(_("Only pending sale price updates can be approved."))
            self.env.cr.execute(
                "SELECT id FROM sale_price_update WHERE id = %s FOR UPDATE NOWAIT",
                [record.id],
            )
            if record.approved_sale_price < 0:
                raise ValidationError(_("Approved Sale Price must be greater than or equal to zero."))
            if not self._get_setting_bool("purchase_sale_price_approval.allow_manual_approved_price", True):
                if float_compare(
                    record.approved_sale_price,
                    record.calculated_sale_price,
                    precision_rounding=record.currency_id.rounding,
                ):
                    raise ValidationError(
                        _("Manual approval price changes are disabled. Approved Sale Price must match the calculated price.")
                    )
            company_currency = record.company_id.currency_id
            current_price_company = record.product_tmpl_id.with_company(record.company_id).list_price
            conversion_date = record.effective_date or fields.Date.context_today(record)
            current_price = company_currency._convert(
                current_price_company,
                record.currency_id,
                record.company_id,
                conversion_date,
            )
            if self._get_setting_bool("purchase_sale_price_approval.block_price_decrease"):
                if float_compare(
                    record.approved_sale_price,
                    current_price,
                    precision_rounding=record.currency_id.rounding,
                ) < 0:
                    raise ValidationError(
                        _("Approved Sale Price cannot be lower than the current product sale price.")
                    )
            approved_sale_price_company = record.currency_id._convert(
                record.approved_sale_price,
                company_currency,
                record.company_id,
                conversion_date,
            )
            record.product_tmpl_id.with_company(record.company_id).write(
                {"list_price": approved_sale_price_company}
            )
            record.with_context(skip_sale_price_update_protection=True).write(
                {
                    "state": "approved",
                    "approved_by": self.env.user.id,
                    "approved_date": fields.Datetime.now(),
                }
            )
            record._post_approval_messages()
            record._create_history_record()
            record._supersede_older_pending_updates()
        return True

    def action_reject(self):
        self._check_manager_access()
        for record in self:
            record.ensure_one()
            if record.state != "pending":
                raise UserError(_("Only pending sale price updates can be rejected."))
            if not record.rejection_reason:
                raise ValidationError(_("Rejection Reason is required before rejecting a sale price update."))
            record.with_context(skip_sale_price_update_protection=True).write(
                {
                    "state": "rejected",
                    "rejected_by": self.env.user.id,
                    "rejected_date": fields.Datetime.now(),
                }
            )
            record.message_post(body=_("Sale price update rejected."))
            record.purchase_order_id.message_post(
                body=_(
                    "Sale Price Update %(update)s rejected for product %(product)s."
                )
                % {
                    "update": record.display_name,
                    "product": record.product_id.display_name,
                }
            )
        return True

    def action_cancel(self):
        for record in self:
            if record.state != "pending":
                raise UserError(_("Only pending sale price updates can be cancelled."))
            record.with_context(skip_sale_price_update_protection=True).write({"state": "cancelled"})
            record.message_post(body=_("Sale price update cancelled."))
        return True

    def action_reset_to_pending(self):
        self._check_manager_access()
        for record in self:
            if record.state not in ("rejected", "cancelled"):
                raise UserError(_("Only rejected or cancelled records can be reset to pending."))
            record.with_context(skip_sale_price_update_protection=True).write(
                {
                    "state": "pending",
                    "rejected_by": False,
                    "rejected_date": False,
                    "rejection_reason": False,
                }
            )
            record.message_post(body=_("Sale price update reset to pending."))
        return True

    def unlink(self):
        if any(record.state in ("approved", "rejected", "cancelled", "superseded") for record in self):
            raise UserError(_("Approved sale price updates cannot be deleted."))
        return super().unlink()
