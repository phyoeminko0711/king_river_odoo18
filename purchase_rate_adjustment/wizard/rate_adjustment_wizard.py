from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero


class PurchaseRateAdjustmentWizard(models.TransientModel):
    _name = "purchase.rate.adjustment.wizard"
    _description = "Apply Product Rate Adjustment"

    rate_ids = fields.Many2many(
        "product.rate.scheme",
        string="Rates",
        required=True,
    )
    amount_per_kg = fields.Monetary(
        string="Amount per KG",
        currency_field="currency_id",
        required=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    user_id = fields.Many2one(
        "res.users",
        string="Responsible Person",
        default=lambda self: self.env.user,
        readonly=True,
    )
    state = fields.Selection(
        [("draft", "Draft"), ("applied", "Applied")],
        default="draft",
        required=True,
    )

    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group("purchase.group_purchase_manager"):
            raise UserError(_("Only Purchase Managers can apply rate adjustments."))
        if self.company_id not in self.env.companies:
            raise UserError(_("Select an allowed company for this adjustment."))
        self.env.cr.execute(
            "SELECT id FROM purchase_rate_adjustment_wizard WHERE id = %s FOR UPDATE",
            [self.id],
        )
        self.invalidate_recordset(["state"])
        if self.state != "draft":
            raise UserError(_("This rate adjustment has already been applied."))
        if not self.rate_ids:
            raise ValidationError(_("Select at least one rate."))
        if float_is_zero(self.amount_per_kg, precision_rounding=0.000001):
            raise ValidationError(_("Amount per KG must not be zero."))

        products = self.env["product.template"].search(
            [
                ("rate_scheme_id", "in", self.rate_ids.ids),
                ("company_id", "in", [False, self.company_id.id]),
            ],
            order="id",
        )
        if not products:
            raise UserError(_("No products with the selected rates were found."))
        missing_weight = products.filtered(lambda product: product.weight <= 0)
        if missing_weight:
            raise ValidationError(
                _("Set a positive weight for these products before applying the adjustment: %s")
                % ", ".join(missing_weight.mapped("display_name"))
            )

        self.env.cr.execute(
            "SELECT id FROM product_template WHERE id = ANY(%s) ORDER BY id FOR UPDATE",
            [products.ids],
        )
        products.invalidate_recordset(["list_price", "weight"])
        weight_uom = products._get_weight_uom_id_from_ir_config_parameter()
        kg_uom = self.env.ref("uom.product_uom_kgm")
        new_prices = []
        for product in products:
            weight_kg = weight_uom._compute_quantity(
                product.weight, kg_uom, round=False
            )
            new_price = self.company_id.currency_id.round(
                product.list_price + weight_kg * self.amount_per_kg
            )
            if new_price < 0:
                raise ValidationError(
                    _("The adjustment would make the sales price negative for %s.")
                    % product.display_name
                )
            new_prices.append((product, new_price))

        for product, new_price in new_prices:
            product.sudo().write({"list_price": new_price})

        self.env["purchase.rate.adjustment"].sudo().with_context(
            from_rate_adjustment_wizard=True
        ).create(
            {
                "rate_ids": [fields.Command.set(self.rate_ids.ids)],
                "amount_per_kg": self.amount_per_kg,
                "company_id": self.company_id.id,
                "user_id": self.env.user.id,
                "applied_at": fields.Datetime.now(),
                "product_count": len(products),
            }
        )
        self.state = "applied"
        return {"type": "ir.actions.act_window_close"}
