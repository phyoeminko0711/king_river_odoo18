from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    repair_move_id = fields.Many2one(
        "stock.move",
        string="Repair Line",
        readonly=True,
        copy=False,
        index=True,
        ondelete="restrict",
    )
    repair_charge_line_id = fields.Many2one(
        "workshop.repair.charge.line",
        string="Repair Service Charge",
        readonly=True,
        copy=False,
        index=True,
        ondelete="restrict",
    )
