import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)


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
    company_currency_id = fields.Many2one(
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    purchase_order_id = fields.Many2one("purchase.order", ondelete="restrict", index=True)
    purchase_order_line_id = fields.Many2one(
        "purchase.order.line",
        ondelete="restrict",
        index=True,
    )
    landed_cost_id = fields.Many2one(
        "stock.landed.cost",
        string="Landed Cost",
        ondelete="restrict",
        index=True,
        check_company=True,
    )
    valuation_adjustment_line_ids = fields.Many2many(
        "stock.valuation.adjustment.lines",
        "sale_price_update_valuation_rel",
        "update_id",
        "valuation_line_id",
        string="Valuation Adjustment Lines",
    )
    cost_source = fields.Selection(
        [
            ("purchase", "Purchase Price"),
            ("landed_cost", "Landed Cost"),
            ("currency_revaluation", "Currency Revaluation"),
        ],
        default="landed_cost",
        required=True,
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
    foreign_purchase_unit_price = fields.Monetary(
        string="Foreign PO Unit Price",
        currency_field="source_currency_id",
        readonly=True,
    )
    original_conversion_date = fields.Date(readonly=True)
    original_currency_value = fields.Monetary(
        string="Original Currency Value",
        currency_field="company_currency_id",
        readonly=True,
        help="Company-currency value of one unit of the source currency at the original costing date.",
    )
    original_purchase_cost_company = fields.Monetary(
        string="Original Purchase Cost",
        currency_field="company_currency_id",
        readonly=True,
    )
    landed_cost_unit_amount = fields.Monetary(
        string="Landed Cost Allocation",
        currency_field="company_currency_id",
        readonly=True,
    )
    original_total_cost = fields.Monetary(
        string="Original Total Cost",
        currency_field="company_currency_id",
        readonly=True,
    )
    previous_revaluation_date = fields.Date(readonly=True)
    revaluation_date = fields.Date(readonly=True)
    previous_currency_value = fields.Monetary(
        string="Previous Currency Value",
        currency_field="company_currency_id",
        readonly=True,
    )
    current_currency_value = fields.Monetary(
        string="New Currency Value",
        currency_field="company_currency_id",
        readonly=True,
    )
    previous_exchange_rate_value = fields.Monetary(
        string="Previous Exchange Rate Value",
        currency_field="company_currency_id",
        readonly=True,
        help="Company-currency value of exactly one unit of the source currency at the previous baseline date.",
    )
    current_exchange_rate_value = fields.Monetary(
        string="Current Exchange Rate Value",
        currency_field="company_currency_id",
        readonly=True,
        help="Company-currency value of exactly one unit of the source currency at the revaluation date.",
    )
    previous_converted_purchase_cost = fields.Monetary(
        string="Previous Converted Purchase Cost",
        currency_field="company_currency_id",
        readonly=True,
    )
    current_converted_purchase_cost = fields.Monetary(
        string="Current Converted Purchase Cost",
        currency_field="company_currency_id",
        readonly=True,
    )
    previous_cost_basis = fields.Monetary(
        string="Previous Cost Basis",
        currency_field="company_currency_id",
        readonly=True,
    )
    revalued_cost_basis = fields.Monetary(
        string="Revalued Cost Basis",
        currency_field="company_currency_id",
        readonly=True,
    )
    revalued_purchase_cost = fields.Monetary(
        string="Revalued Purchase Cost",
        currency_field="company_currency_id",
        readonly=True,
    )
    cost_difference = fields.Monetary(
        string="Cost Difference",
        currency_field="company_currency_id",
        readonly=True,
    )
    cost_difference_percentage = fields.Float(readonly=True)
    last_revaluation_date = fields.Date(readonly=True)
    last_revaluation_rate = fields.Monetary(
        string="Last Revaluation Currency Value",
        currency_field="company_currency_id",
        readonly=True,
    )
    last_revalued_cost = fields.Monetary(
        string="Last Revalued Cost",
        currency_field="company_currency_id",
        readonly=True,
    )
    last_sale_price = fields.Monetary(
        string="Last Sale Price",
        currency_field="currency_id",
        readonly=True,
    )
    converted_purchase_price = fields.Monetary(readonly=True, currency_field="currency_id")
    landed_unit_cost = fields.Monetary(
        string="Landed Unit Cost",
        currency_field="currency_id",
        readonly=True,
    )
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
        string="Status",
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

    def init(self):
        self.env.cr.execute(
            """
            UPDATE sale_price_update
               SET cost_source = 'purchase'
             WHERE landed_cost_id IS NULL
               AND purchase_order_id IS NOT NULL
               AND (cost_source IS NULL OR cost_source = 'landed_cost')
            """
        )
        self.env.cr.execute(
            """
            UPDATE sale_price_update
               SET previous_exchange_rate_value = COALESCE(previous_exchange_rate_value, original_currency_value),
                   current_exchange_rate_value = COALESCE(current_exchange_rate_value, original_currency_value),
                   previous_converted_purchase_cost = COALESCE(
                       previous_converted_purchase_cost,
                       previous_currency_value,
                       original_purchase_cost_company
                   ),
                   current_converted_purchase_cost = COALESCE(
                       current_converted_purchase_cost,
                       current_currency_value,
                       original_purchase_cost_company
                   )
             WHERE source_currency_id IS NOT NULL
            """
        )

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = sequence.next_by_code("sale.price.update") or "New"
            if not vals.get("cost_source") and vals.get("purchase_order_id") and not vals.get("landed_cost_id"):
                vals["cost_source"] = "purchase"
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
    def _round_sale_price(self, amount, currency):
        return currency.round(amount)

    @api.model
    def _calculate_sale_price(self, purchase_price, markup_type, markup_value, currency):
        if markup_type == "percentage":
            proposed_price = purchase_price + (purchase_price * markup_value / 100.0)
        else:
            proposed_price = purchase_price + markup_value
        return self._round_sale_price(proposed_price, currency)

    def _has_meaningful_update_change(self, new_vals):
        """Return whether stored pricing data differs from proposed values."""
        self.ensure_one()
        monetary_fields = [
            "purchase_price",
            "converted_purchase_price",
            "landed_unit_cost",
            "foreign_purchase_unit_price",
            "original_purchase_cost_company",
            "landed_cost_unit_amount",
            "original_total_cost",
            "previous_currency_value",
            "current_currency_value",
            "previous_exchange_rate_value",
            "current_exchange_rate_value",
            "previous_converted_purchase_cost",
            "current_converted_purchase_cost",
            "previous_cost_basis",
            "revalued_cost_basis",
            "old_sale_price",
            "calculated_sale_price",
            "approved_sale_price",
        ]
        for field_name in monetary_fields:
            if self[field_name] != new_vals.get(field_name):
                return True
        comparable_fields = [
            "currency_id",
            "source_currency_id",
            "rule_line_id",
            "effective_date",
            "conversion_date",
            "original_conversion_date",
            "revaluation_date",
            "cost_source",
        ]
        for field_name in comparable_fields:
            current_value = self[field_name]
            proposed_value = new_vals.get(field_name)
            if hasattr(current_value, "id"):
                current_value = current_value.id
            if current_value != proposed_value:
                return True
        return False

    def _get_normalized_purchase_line_foreign_unit_price(self):
        self.ensure_one()
        purchase_line = self.purchase_order_line_id
        if not purchase_line:
            return 0.0
        return purchase_line.product_uom._compute_price(
            purchase_line.price_unit,
            self.product_id.uom_id,
        )

    def _log_invalid_currency_revaluation_source(self, source, reason):
        _logger.warning(
            "Skipping currency revaluation source %s for product %s: %s",
            source.display_name,
            source.product_id.display_name,
            reason,
        )

    def _is_valid_currency_revaluation_source(self):
        self.ensure_one()
        company_currency = self.company_id.currency_id
        if not self.source_currency_id or self.source_currency_id == company_currency:
            self._log_invalid_currency_revaluation_source(
                self,
                "source currency is missing or is the company currency",
            )
            return False
        if (
            float_compare(
                self.foreign_purchase_unit_price,
                0.0,
                precision_rounding=self.source_currency_id.rounding,
            )
            <= 0
        ):
            self._log_invalid_currency_revaluation_source(
                self,
                "foreign purchase unit price is not positive",
            )
            return False
        if not self.purchase_order_line_id:
            self._log_invalid_currency_revaluation_source(
                self,
                "source purchase order line is missing",
            )
            return False
        if self.purchase_order_line_id.order_id.currency_id != self.source_currency_id:
            self._log_invalid_currency_revaluation_source(
                self,
                "source purchase order currency does not match the stored source currency",
            )
            return False
        normalized_price = self._get_normalized_purchase_line_foreign_unit_price()
        if (
            float_compare(
                self.foreign_purchase_unit_price,
                normalized_price,
                precision_rounding=self.source_currency_id.rounding,
            )
            != 0
        ):
            self._log_invalid_currency_revaluation_source(
                self,
                _(
                    "stored foreign purchase unit price %(stored)s does not match PO line unit price %(actual)s"
                )
                % {
                    "stored": self.foreign_purchase_unit_price,
                    "actual": normalized_price,
                },
            )
            return False
        return True

    def _get_latest_currency_revaluation_sources(self):
        """Return latest reliable approved foreign-currency pricing source per product/company/currency."""
        domain = [
            ("state", "=", "approved"),
            ("cost_source", "in", ["landed_cost", "currency_revaluation"]),
            ("product_id.active", "=", True),
            ("foreign_purchase_unit_price", ">", 0.0),
            ("original_purchase_cost_company", ">", 0.0),
            ("landed_cost_unit_amount", ">=", 0.0),
            ("source_currency_id", "!=", False),
            ("rule_line_id", "!=", False),
        ]
        candidates = self.sudo().search(
            domain,
            order="effective_date desc, approved_date desc, id desc",
        )
        sources = self.browse()
        seen = set()
        for candidate in candidates:
            if not candidate._is_valid_currency_revaluation_source():
                continue
            key = (candidate.company_id.id, candidate.product_id.id, candidate.source_currency_id.id)
            if key in seen:
                continue
            seen.add(key)
            sources |= candidate
        return sources

    def _prepare_currency_revaluation_values(self, source, revaluation_date):
        company = source.company_id
        company_currency = company.currency_id
        source_currency = source.source_currency_id
        rule_line = source.rule_line_id
        if not rule_line:
            return False

        previous_revaluation_date = (
            source.revaluation_date
            or source.last_revaluation_date
            or source.original_conversion_date
            or source.effective_date
        )
        previous_exchange_rate_value = (
            source.current_exchange_rate_value
            or source.original_currency_value
            or source.source_currency_id._convert(1.0, company_currency, company, previous_revaluation_date)
        )
        current_exchange_rate_value = source_currency._convert(
            1.0,
            company_currency,
            company,
            revaluation_date,
        )
        previous_converted_purchase_cost = (
            source.current_converted_purchase_cost
            or source.current_currency_value
            or source.original_purchase_cost_company
        )
        previous_cost_basis = source.revalued_cost_basis or source.original_total_cost
        current_converted_purchase_cost = source_currency._convert(
            source.foreign_purchase_unit_price,
            company_currency,
            company,
            revaluation_date,
        )
        if (
            float_compare(
                current_converted_purchase_cost,
                previous_converted_purchase_cost,
                precision_rounding=company_currency.rounding,
            )
            <= 0
        ):
            return False

        revalued_cost_basis = current_converted_purchase_cost + source.landed_cost_unit_amount
        rule_currency = rule_line.currency_id
        revalued_cost_rule_currency = company_currency._convert(
            revalued_cost_basis,
            rule_currency,
            company,
            revaluation_date,
        )
        calculated_sale_price = self._calculate_sale_price(
            revalued_cost_rule_currency,
            source.markup_type,
            source.markup_value,
            rule_currency,
        )
        current_sale_company = source.product_tmpl_id.with_company(company).list_price
        current_sale_rule_currency = company_currency._convert(
            current_sale_company,
            rule_currency,
            company,
            revaluation_date,
        )
        if (
            float_compare(
                calculated_sale_price,
                current_sale_rule_currency,
                precision_rounding=rule_currency.rounding,
            )
            <= 0
        ):
            return False

        cost_difference = revalued_cost_basis - (previous_cost_basis or 0.0)
        cost_difference_percentage = (
            (cost_difference / previous_cost_basis) * 100.0 if previous_cost_basis else 0.0
        )
        return {
            "company_id": company.id,
            "currency_id": rule_currency.id,
            "product_id": source.product_id.id,
            "purchase_order_id": source.purchase_order_id.id or False,
            "purchase_order_line_id": source.purchase_order_line_id.id or False,
            "landed_cost_id": source.landed_cost_id.id or False,
            "valuation_adjustment_line_ids": [(6, 0, source.valuation_adjustment_line_ids.ids)],
            "purchase_quantity": source.purchase_quantity,
            "purchase_uom_id": source.purchase_uom_id.id or source.product_id.uom_id.id,
            "purchase_price": source.foreign_purchase_unit_price,
            "source_currency_id": source_currency.id,
            "foreign_purchase_unit_price": source.foreign_purchase_unit_price,
            "original_conversion_date": source.original_conversion_date,
            "original_currency_value": source.original_currency_value,
            "original_purchase_cost_company": source.original_purchase_cost_company,
            "landed_cost_unit_amount": source.landed_cost_unit_amount,
            "original_total_cost": source.original_total_cost,
            "previous_revaluation_date": previous_revaluation_date,
            "revaluation_date": revaluation_date,
            "previous_currency_value": previous_converted_purchase_cost,
            "current_currency_value": current_converted_purchase_cost,
            "previous_exchange_rate_value": previous_exchange_rate_value,
            "current_exchange_rate_value": current_exchange_rate_value,
            "previous_converted_purchase_cost": previous_converted_purchase_cost,
            "current_converted_purchase_cost": current_converted_purchase_cost,
            "previous_cost_basis": previous_cost_basis,
            "revalued_purchase_cost": current_converted_purchase_cost,
            "revalued_cost_basis": revalued_cost_basis,
            "cost_difference": cost_difference,
            "cost_difference_percentage": cost_difference_percentage,
            "last_revaluation_date": revaluation_date,
            "last_revaluation_rate": current_exchange_rate_value,
            "last_revalued_cost": revalued_cost_basis,
            "last_sale_price": calculated_sale_price,
            "converted_purchase_price": revalued_cost_rule_currency,
            "landed_unit_cost": revalued_cost_rule_currency,
            "old_sale_price": current_sale_rule_currency,
            "markup_type": source.markup_type,
            "markup_value": source.markup_value,
            "calculated_sale_price": calculated_sale_price,
            "approved_sale_price": calculated_sale_price,
            "rule_line_id": rule_line.id,
            "effective_date": revaluation_date,
            "conversion_date": revaluation_date,
            "requested_by": self.env.user.id,
            "approved_by": self.env.user.id,
            "approved_date": fields.Datetime.now(),
            "state": "approved",
            "cost_source": "currency_revaluation",
            "previous_update_id": source.id,
            "note": _("Automatically applied by Currency Sale Price Revaluation scheduled action."),
        }

    def _find_duplicate_currency_revaluation(self, vals):
        duplicates = self.sudo().search(
            [
                ("company_id", "=", vals["company_id"]),
                ("product_id", "=", vals["product_id"]),
                ("source_currency_id", "=", vals["source_currency_id"]),
                ("cost_source", "=", "currency_revaluation"),
                ("state", "=", "approved"),
                ("revaluation_date", "=", vals["revaluation_date"]),
            ],
            order="id desc",
        )
        company_currency = self.env["res.company"].browse(vals["company_id"]).currency_id
        rule_currency = self.env["res.currency"].browse(vals["currency_id"])
        for duplicate in duplicates:
            same_cost = (
                float_compare(
                    duplicate.current_converted_purchase_cost or duplicate.current_currency_value,
                    vals["current_converted_purchase_cost"],
                    precision_rounding=company_currency.rounding,
                )
                == 0
            )
            same_price = (
                float_compare(
                    duplicate.calculated_sale_price,
                    vals["calculated_sale_price"],
                    precision_rounding=rule_currency.rounding,
                )
                == 0
            )
            if same_cost and same_price:
                return duplicate
        return self.browse()

    def _log_applied_currency_revaluation(self):
        self.ensure_one()
        company_currency = self.company_id.currency_id
        source_currency = self.source_currency_id
        markup = (
            "%s%%" % self.markup_value
            if self.markup_type == "percentage"
            else "%s" % self.markup_value
        )
        _logger.info(
            "\nCurrency revaluation applied:\n"
            "Product [%s] %s\n"
            "Currency: %s\n"
            "Foreign PO Unit Price: %s\n"
            "Previous Rate: %s %s/%s\n"
            "Current Rate: %s %s/%s\n"
            "Previous Purchase Cost: %s\n"
            "Current Purchase Cost: %s\n"
            "Landed Cost: %s\n"
            "Previous Cost Basis: %s\n"
            "New Cost Basis: %s\n"
            "Markup: %s\n"
            "Old Sale Price: %s\n"
            "New Sale Price: %s\n"
            "Revaluation Date: %s\n"
            "History ID: %s",
            self.product_id.id,
            self.product_id.display_name,
            source_currency.name,
            source_currency.format(self.foreign_purchase_unit_price),
            company_currency.format(self.previous_exchange_rate_value),
            company_currency.name,
            source_currency.name,
            company_currency.format(self.current_exchange_rate_value),
            company_currency.name,
            source_currency.name,
            company_currency.format(self.previous_converted_purchase_cost),
            company_currency.format(self.current_converted_purchase_cost),
            company_currency.format(self.landed_cost_unit_amount),
            company_currency.format(self.previous_cost_basis),
            company_currency.format(self.revalued_cost_basis),
            markup,
            self.currency_id.format(self.old_sale_price),
            self.currency_id.format(self.approved_sale_price),
            self.revaluation_date,
            self.id,
        )

    def _apply_currency_revaluation_values(self, vals):
        duplicate = self._find_duplicate_currency_revaluation(vals)
        if duplicate:
            _logger.info(
                "Skipping duplicate currency revaluation for product %s on %s; existing update: %s.",
                duplicate.product_id.display_name,
                vals["revaluation_date"],
                duplicate.display_name,
            )
            return duplicate, False
        update = self.sudo().create(vals)
        company = update.company_id
        company_currency = company.currency_id
        approved_sale_price_company = update.currency_id._convert(
            update.approved_sale_price,
            company_currency,
            company,
            update.revaluation_date or update.effective_date,
        )
        update.product_tmpl_id.with_company(company).sudo().write(
            {"list_price": approved_sale_price_company}
        )
        update.message_post(
            body=_(
                "Currency revaluation automatically increased the sale price from %(old)s to %(new)s."
            )
            % {
                "old": update.old_sale_price,
                "new": update.approved_sale_price,
            }
        )
        if hasattr(update.product_tmpl_id, "message_post"):
            update.product_tmpl_id.message_post(
                body=_(
                    "Sale price increased by currency revaluation %(update)s. Old price: %(old)s, new price: %(new)s."
                )
                % {
                    "update": update.display_name,
                    "old": update.old_sale_price,
                    "new": update.approved_sale_price,
                }
            )
        update._log_applied_currency_revaluation()
        return update, True

    @api.model
    def _cron_currency_sale_price_revaluation(self):
        revaluation_date = self.env.context.get(
            "revaluation_date",
            fields.Date.context_today(self),
        )
        sources = self._get_latest_currency_revaluation_sources()
        evaluated = created = skipped_rate = skipped_invalid = skipped_price = skipped_duplicate = 0
        for source in sources:
            evaluated += 1
            try:
                with self.env.cr.savepoint():
                    vals = self._prepare_currency_revaluation_values(source, revaluation_date)
                    if not vals:
                        previous_converted_purchase_cost = (
                            source.current_converted_purchase_cost
                            or source.current_currency_value
                            or source.original_purchase_cost_company
                        )
                        current_converted_purchase_cost = source.source_currency_id._convert(
                            source.foreign_purchase_unit_price,
                            source.company_id.currency_id,
                            source.company_id,
                            revaluation_date,
                        )
                        if (
                            float_compare(
                                current_converted_purchase_cost,
                                previous_converted_purchase_cost,
                                precision_rounding=source.company_id.currency_id.rounding,
                            )
                            <= 0
                        ):
                            skipped_rate += 1
                        else:
                            skipped_price += 1
                        continue
                    _update, did_create = self._apply_currency_revaluation_values(vals)
                    if not did_create:
                        skipped_duplicate += 1
                        continue
                    created += 1
            except Exception:
                skipped_invalid += 1
                _logger.exception(
                    "Currency sale price revaluation skipped product %s due to invalid source data.",
                    source.product_id.display_name,
                )
        _logger.info(
            "Currency Sale Price Revaluation completed. Products evaluated: %s; "
            "Prices increased: %s; Skipped - same/lower rate: %s; "
            "Skipped - calculated price not higher: %s; Skipped - duplicate: %s; "
            "Skipped - invalid source: %s.",
            evaluated,
            created,
            skipped_rate,
            skipped_price,
            skipped_duplicate,
            skipped_invalid,
        )
        return True

    def _post_approval_messages(self):
        self.ensure_one()
        self.message_post(
            body=_("Sale price approved. Product sale price updated to %s.") % self.approved_sale_price
        )
        if self.purchase_order_id:
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
        if self.landed_cost_id:
            self.landed_cost_id.message_post(
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
            source_label = (
                self.purchase_order_id.display_name
                or self.landed_cost_id.display_name
                or dict(self._fields["cost_source"].selection).get(self.cost_source)
                or _("manual update")
            )
            self.product_tmpl_id.message_post(
                body=_(
                    "Sale price updated from %(source)s through Sale Price Update %(update)s. "
                    "Old price: %(old)s, new price: %(new)s."
                )
                % {
                    "source": source_label,
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
            company_currency = record.company_id.currency_id
            conversion_date = record.effective_date or fields.Date.context_today(record)
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
            body = _(
                "Sale Price Update %(update)s rejected for product %(product)s."
            ) % {
                "update": record.display_name,
                "product": record.product_id.display_name,
            }
            if record.purchase_order_id:
                record.purchase_order_id.message_post(body=body)
            if record.landed_cost_id:
                record.landed_cost_id.message_post(body=body)
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
