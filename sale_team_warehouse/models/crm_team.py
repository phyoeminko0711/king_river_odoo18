from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CrmTeam(models.Model):
    _inherit = "crm.team"

    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Warehouse",
        help="Default warehouse used for quotations and sales orders assigned to this Sales Team.",
    )

    @api.constrains("company_id", "warehouse_id")
    def _check_warehouse_company(self):
        for team in self:
            if (
                team.company_id
                and team.warehouse_id
                and team.warehouse_id.company_id != team.company_id
            ):
                raise ValidationError(
                    _("The selected Warehouse must belong to the same company as the Sales Team.")
                )
