from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    repair_order_id = fields.Many2one(
        "repair.order",
        string="Repair Order",
        readonly=True,
        copy=False,
        index=True,
        ondelete="restrict",
        check_company=True,
    )
