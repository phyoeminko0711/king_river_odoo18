from odoo import api, fields, models


class WorkshopRepairService(models.Model):
    _name = "workshop.repair.service"
    _description = "Workshop Repair Service"
    _order = "sequence, name"

    name = fields.Char(string="Repair Service", required=True, index=True)
    code = fields.Char(index=True)
    product_ids = fields.Many2many(
        "product.product",
        string="Product Options",
    )
    product_option_count = fields.Integer(
        string="Product Option Count",
        compute="_compute_product_option_count",
    )
    active = fields.Boolean(default=True)
    description = fields.Text()
    sequence = fields.Integer(default=10)

    @api.depends("product_ids")
    def _compute_product_option_count(self):
        for service in self:
            service.product_option_count = len(service.product_ids)
