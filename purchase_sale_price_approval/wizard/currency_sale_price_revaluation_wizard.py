from odoo import _, fields, models
from odoo.exceptions import ValidationError


class CurrencySalePriceRevaluationWizard(models.TransientModel):
    _name = "currency.sale.price.revaluation.wizard"
    _description = "Currency Sale Price Revaluation Wizard"

    revaluation_date = fields.Date(
        required=True,
        default=lambda self: fields.Date.context_today(self),
    )
    currency_id = fields.Many2one("res.currency", required=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    product_ids = fields.Many2many("product.product", string="Products")
    product_category_id = fields.Many2one("product.category", string="Product Category")

    def action_calculate_create_updates(self):
        self.ensure_one()
        if not self.env.user.has_group("purchase_sale_price_approval.group_sale_price_manager"):
            raise ValidationError(_("Only Sale Price Managers can run currency revaluation."))

        result = self.env["sale.price.update"]._run_currency_sale_price_revaluation(
            self.currency_id,
            self.company_id,
            self.revaluation_date,
            product_ids=self.product_ids,
            product_category=self.product_category_id,
        )
        message = _(
            "Currency revaluation completed. Products evaluated: %(evaluated)s. "
            "Pending updates created: %(created)s. Skipped because currency cost did not increase: %(no_increase)s. "
            "Skipped because proposed price was not above current sale price: %(not_above)s. "
            "Missing source/rule records: %(missing)s. Duplicates skipped: %(duplicates)s. "
            "Pending updates superseded: %(superseded)s. Stale pending updates cancelled: %(cancelled)s."
        ) % {
            "evaluated": result["evaluated"],
            "created": len(result["created_updates"]),
            "no_increase": result["skipped_no_increase"],
            "not_above": result["skipped_not_above_sale"],
            "missing": result["skipped_missing_source"],
            "duplicates": result["duplicates"],
            "superseded": result["superseded"],
            "cancelled": result["cancelled"],
        }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Currency Price Revaluation"),
                "message": message,
                "type": "success" if result["created_updates"] else "warning",
                "sticky": True,
            },
        }
