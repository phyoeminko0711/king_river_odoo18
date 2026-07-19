from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError


class WorkshopRemoveRepairServiceWizard(models.TransientModel):
    _name = "workshop.remove.repair.service.wizard"
    _description = "Remove Repair Services from Job Card"

    job_card_id = fields.Many2one(
        "workshop.job.card",
        string="Job Card",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    # Kept technically optional so the object method can provide the requested
    # friendly validation instead of the generic required-field message.
    job_card_service_ids = fields.Many2many(
        "workshop.job.card.service",
        "workshop_remove_service_wizard_rel",
        "wizard_id",
        "job_card_service_id",
        string="Repair Services",
    )

    def action_remove_services(self):
        self.ensure_one()
        if not self.job_card_service_ids:
            raise ValidationError(
                _("Please select at least one Repair Service to remove.")
            )

        job_card = self.job_card_id
        if job_card.state not in {"draft", "sent"}:
            raise UserError(
                _(
                    "Repair Services can only be removed while the Job Card is "
                    "in Draft or Sent to Customer state."
                )
            )

        invalid_services = self.job_card_service_ids.filtered(
            lambda service: service.job_card_id != job_card
        )
        if invalid_services:
            raise ValidationError(
                _("Only Repair Services from the current Job Card can be removed.")
            )

        # Direct service deletion remains unavailable through the normal ACL.
        # This narrowly scoped wizard deletion runs only after the ownership and
        # state checks above; option lines follow the database cascade.
        self.job_card_service_ids.sudo().unlink()
        job_card.invalidate_recordset(
            ["service_line_ids", "line_ids", "total_amount", "selected_line_count"]
        )
        job_card._compute_total_amount()
        job_card._compute_selected_line_count()
        return {"type": "ir.actions.client", "tag": "reload"}
