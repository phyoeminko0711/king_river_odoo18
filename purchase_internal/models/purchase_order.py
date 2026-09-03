from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analytic Account",
        check_company=True,
        tracking=True,
    )

    def _get_header_analytic_distribution(self):
        self.ensure_one()
        if not self.analytic_account_id:
            return False
        return {str(self.analytic_account_id.id): 100.0}

    def _apply_header_analytic_distribution(self):
        for order in self:
            distribution = order._get_header_analytic_distribution()
            order.order_line.filtered(lambda line: not line.display_type).analytic_distribution = distribution

    @api.onchange("analytic_account_id")
    def _onchange_analytic_account_id(self):
        self._apply_header_analytic_distribution()

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order, vals in zip(orders, vals_list):
            if vals.get("analytic_account_id"):
                order._apply_header_analytic_distribution()
        return orders

    def write(self, vals):
        result = super().write(vals)
        if "analytic_account_id" in vals:
            self._apply_header_analytic_distribution()
        return result
