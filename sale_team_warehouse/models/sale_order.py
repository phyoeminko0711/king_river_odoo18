from odoo import _, api, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_sales_team_warehouse(self, team, company):
        """Return the team's warehouse after validating company consistency."""
        if not team or not team.warehouse_id:
            return self.env["stock.warehouse"]
        warehouse = team.warehouse_id
        if company and warehouse.company_id and warehouse.company_id != company:
            raise ValidationError(
                _("The selected Warehouse must belong to the same company as the Sales Team.")
            )
        return warehouse

    def _apply_sales_team_warehouse(self):
        """Set the sale order warehouse from its sales team when configured."""
        for order in self:
            warehouse = order._get_sales_team_warehouse(order.team_id, order.company_id)
            if warehouse:
                order.warehouse_id = warehouse

    @api.onchange("team_id")
    def _onchange_team_id_set_warehouse(self):
        self._apply_sales_team_warehouse()

    @api.onchange("user_id")
    def _onchange_user_id_set_team_warehouse(self):
        self._compute_team_id()
        self._apply_sales_team_warehouse()

    @api.model_create_multi
    def create(self, vals_list):
        team_model = self.env["crm.team"]
        for vals in vals_list:
            team_id = vals.get("team_id")
            if team_id and "warehouse_id" not in vals:
                company = self.env["res.company"].browse(
                    vals.get("company_id") or self.env.company.id
                )
                warehouse = self._get_sales_team_warehouse(team_model.browse(team_id), company)
                if warehouse:
                    vals["warehouse_id"] = warehouse.id

        orders = super().create(vals_list)

        for order, vals in zip(orders, vals_list):
            if "warehouse_id" not in vals and order.team_id.warehouse_id:
                order.with_context(skip_sale_team_warehouse=True)._apply_sales_team_warehouse()
        return orders

    def write(self, vals):
        result = super().write(vals)
        if (
            not self.env.context.get("skip_sale_team_warehouse")
            and "warehouse_id" not in vals
            and ("team_id" in vals or "user_id" in vals)
        ):
            self.with_context(skip_sale_team_warehouse=True)._apply_sales_team_warehouse()
        return result
