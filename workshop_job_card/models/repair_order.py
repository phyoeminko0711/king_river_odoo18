from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RepairOrder(models.Model):
    _inherit = "repair.order"

    job_card_id = fields.Many2one(
        "workshop.job.card",
        string="Job Card",
        readonly=True,
        copy=False,
        ondelete="restrict",
        index=True,
    )
    customer_vehicle_id = fields.Many2one(
        "workshop.customer.vehicle",
        string="Customer Vehicle",
        readonly=True,
        copy=False,
        ondelete="restrict",
        index=True,
    )
    technician_id = fields.Many2one(
        "hr.employee",
        string="Technician",
        tracking=True,
        check_company=True,
    )
    testing_driver_id = fields.Many2one(
        "hr.employee",
        string="Testing Driver",
        tracking=True,
        check_company=True,
    )
    assistant_technician_id = fields.Many2one(
        "hr.employee",
        string="Assistant Technician",
        tracking=True,
        check_company=True,
    )
    # Upgrade compatibility for the first module version. Its inherited Repair
    # view referenced ``vehicle_id`` and can still be present until an upgrade
    # finishes obsolete-record cleanup. Keep this alias out of current views.
    vehicle_id = fields.Many2one(
        related="customer_vehicle_id",
        string="Legacy Customer Vehicle",
        store=True,
        readonly=True,
    )
    delivery_inspection_id = fields.Many2one(
        "workshop.job.card.inspection",
        compute="_compute_delivery_inspection_id",
        string="Delivery Inspection",
    )
    delivery_inspection_state = fields.Selection(
        related="delivery_inspection_id.state",
        string="Delivery Inspection Status",
    )
    delivery_inspection_completed = fields.Boolean(compute="_compute_delivery_inspection_id")

    _sql_constraints = [
        (
            "repair_order_job_card_unique",
            "unique(job_card_id)",
            "Only one Repair Order can be created for a Job Card.",
        )
    ]

    @api.constrains("technician_id", "assistant_technician_id", "testing_driver_id")
    def _check_unique_employee_roles(self):
        for repair in self:
            employees = (
                repair.technician_id
                | repair.assistant_technician_id
                | repair.testing_driver_id
            )
            selected_count = sum(
                bool(employee)
                for employee in (
                    repair.technician_id,
                    repair.assistant_technician_id,
                    repair.testing_driver_id,
                )
            )
            if len(employees) != selected_count:
                raise ValidationError(
                    _("Technician, Assistant Technician, and Testing Driver must be different employees.")
                )

    def action_view_job_card(self):
        self.ensure_one()
        if not self.job_card_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": "Job Card",
            "res_model": "workshop.job.card",
            "view_mode": "form",
            "res_id": self.job_card_id.id,
        }

    @api.depends("job_card_id.inspection_ids.state", "job_card_id.inspection_ids.inspection_type")
    def _compute_delivery_inspection_id(self):
        for repair in self:
            inspection = repair.job_card_id._get_latest_inspection("delivery_inspection") if repair.job_card_id else False
            repair.delivery_inspection_id = inspection
            repair.delivery_inspection_completed = bool(
                repair.job_card_id and repair.job_card_id._has_completed_inspection("delivery_inspection")
            )

    def action_delivery_inspection(self):
        self.ensure_one()
        if not self.job_card_id:
            raise ValidationError(_("This Repair Order is not linked to a Job Card."))
        if self.delivery_inspection_completed:
            return self.action_view_delivery_inspections()
        return self.job_card_id._open_or_create_inspection(
            "delivery_inspection",
            repair_order=self,
        )

    def action_view_delivery_inspections(self):
        self.ensure_one()
        if not self.job_card_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Delivery Inspections"),
            "res_model": "workshop.job.card.inspection",
            "view_mode": "list,form",
            "domain": [
                ("job_card_id", "=", self.job_card_id.id),
                ("inspection_type", "=", "delivery_inspection"),
            ],
            "context": {"create": False, "delete": False},
        }

    def action_repair_done(self):
        for repair in self:
            if repair.job_card_id and not repair.job_card_id._has_completed_inspection("delivery_inspection"):
                raise ValidationError(_("Complete the Delivery Check before finishing the Repair Order."))
        result = super().action_repair_done()
        for repair in self.filtered("job_card_id"):
            repair.job_card_id._workflow_write({"state": "repair_completed"})
            repair.job_card_id.message_post(body=_("Repair completed after Delivery Inspection."))
        return result


class WorkshopCustomerVehicle(models.Model):
    _inherit = "workshop.customer.vehicle"

    job_card_ids = fields.One2many(
        "workshop.job.card", "vehicle_id", string="Job Cards", readonly=True
    )

    @api.depends("job_card_ids")
    def _compute_job_card_count(self):
        grouped = self.env["workshop.job.card"]._read_group(
            [("vehicle_id", "in", self.ids)], ["vehicle_id"], ["__count"]
        )
        counts = {vehicle.id: count for vehicle, count in grouped}
        for vehicle in self:
            vehicle.job_card_count = counts.get(vehicle.id, 0)
