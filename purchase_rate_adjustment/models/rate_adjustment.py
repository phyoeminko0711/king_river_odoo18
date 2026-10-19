from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseRateAdjustment(models.Model):
    _name = "purchase.rate.adjustment"
    _description = "Product Rate Adjustment History"
    _order = "applied_at desc, id desc"

    rate_ids = fields.Many2many(
        "product.rate.scheme",
        "purchase_rate_adjustment_scheme_rel",
        "adjustment_id",
        "rate_id",
        string="Rates",
        required=True,
        readonly=True,
    )
    amount_per_kg = fields.Monetary(
        string="Amount per KG",
        currency_field="currency_id",
        readonly=True,
    )
    company_id = fields.Many2one("res.company", required=True, readonly=True)
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        readonly=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsible Person",
        required=True,
        readonly=True,
    )
    applied_at = fields.Datetime(required=True, readonly=True)
    product_count = fields.Integer(readonly=True)

    def _check_history_creation(self):
        if not self.env.context.get("from_rate_adjustment_wizard"):
            raise UserError(_("Rate adjustment history is created by the wizard only."))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_history_creation()
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(_("Rate adjustment history cannot be edited."))

    def unlink(self):
        raise UserError(_("Rate adjustment history cannot be deleted."))
