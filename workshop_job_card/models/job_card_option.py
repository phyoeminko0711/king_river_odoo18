from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class WorkshopJobCardOption(models.Model):
    _name = "workshop.job.card.option"
    _description = "Job Card Customer Option"
    _rec_name = "product_id"
    _order = "id"

    job_card_id = fields.Many2one(
        "workshop.job.card", required=True, ondelete="cascade", index=True
    )
    product_id = fields.Many2one(
        "product.product",
        string="Option",
        required=True,
        ondelete="restrict",
        domain=[("type", "=", "consu")],
    )
    quantity = fields.Float(
        required=True, default=1.0, digits="Product Unit of Measure"
    )
    selected = fields.Boolean(string="Selected")

    _sql_constraints = [
        (
            "workshop_job_card_option_quantity_positive",
            "check(quantity > 0)",
            "Option quantity must be greater than zero.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        cards = self.env["workshop.job.card"].browse(
            [vals.get("job_card_id") for vals in vals_list if vals.get("job_card_id")]
        )
        if any(card.state in {"approved", "repair_created"} for card in cards):
            raise UserError(_("Options cannot be added to an approved Job Card."))
        return super().create(vals_list)

    def write(self, vals):
        if vals and any(
            option.job_card_id.state in {"approved", "repair_created"}
            for option in self
        ):
            raise UserError(_("Approved Job Card options cannot be modified."))
        return super().write(vals)

    def unlink(self):
        if any(
            option.job_card_id.state in {"approved", "repair_created"}
            for option in self
        ):
            raise UserError(_("Approved Job Card options cannot be deleted."))
        return super().unlink()

    @api.constrains("quantity")
    def _check_quantity(self):
        if any(option.quantity <= 0 for option in self):
            raise ValidationError(_("Option quantity must be greater than zero."))
