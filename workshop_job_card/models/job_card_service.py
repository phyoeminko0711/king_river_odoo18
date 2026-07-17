from odoo import fields, models


class WorkshopJobCardService(models.Model):
    """Hidden compatibility model for databases upgraded from the first version."""

    _name = "workshop.job.card.service"
    _description = "Legacy Job Card Service"
    _order = "id"

    job_card_id = fields.Many2one(
        "workshop.job.card", required=True, ondelete="cascade", index=True
    )
    name = fields.Char(required=True)
