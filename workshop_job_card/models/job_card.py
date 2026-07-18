from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class WorkshopJobCard(models.Model):
    _name = "workshop.job.card"
    _description = "Workshop Job Card"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "job_card_date desc, id desc"

    _CLOSED_READONLY_FIELDS = {
        "job_card_date",
        "customer_id",
        "vehicle_id",
        "mileage",
        "technician_id",
        "complaint",
        "diagnosis",
        "recommendation",
        "service_line_ids",
        "line_ids",
        "currency_id",
    }
    _WORKFLOW_FIELDS = {
        "name",
        "state",
        "approved_date",
        "approved_by",
        "repair_order_id",
    }

    name = fields.Char(
        string="Job Card Number",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _("New"),
        index=True,
    )
    job_card_date = fields.Datetime(
        string="Job Card Date",
        required=True,
        default=fields.Datetime.now,
        index=True,
        tracking=True,
    )
    customer_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    vehicle_id = fields.Many2one(
        "workshop.customer.vehicle",
        string="Vehicle",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    customer_phone = fields.Char(
        string="Phone", compute="_compute_customer_phone", readonly=True
    )
    plate_no = fields.Char(
        string="Plate Number", related="vehicle_id.plate_no", store=True, readonly=True
    )
    vehicle_brand_id = fields.Many2one(
        related="vehicle_id.vehicle_brand_id",
        string="Vehicle Brand",
        store=True,
        readonly=True,
    )
    vehicle_model_id = fields.Many2one(
        related="vehicle_id.vehicle_model_id",
        string="Vehicle Model",
        store=True,
        readonly=True,
    )
    chassis_no = fields.Char(
        string="Chassis Number",
        related="vehicle_id.chassis_no",
        store=True,
        readonly=True,
    )
    engine_no = fields.Char(
        string="Engine Number",
        related="vehicle_id.engine_no",
        store=True,
        readonly=True,
    )
    color = fields.Char(related="vehicle_id.color", store=True, readonly=True)
    mileage = fields.Float(tracking=True)
    technician_id = fields.Many2one(
        "hr.employee",
        string="Technician",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    technician_job_id = fields.Many2one(
        related="technician_id.job_id",
        string="Position",
        store=True,
        readonly=True,
    )
    complaint = fields.Text(string="Customer Complaint")
    diagnosis = fields.Text(string="Inspection / Diagnosis")
    recommendation = fields.Text(string="Recommendation")
    service_line_ids = fields.One2many(
        "workshop.job.card.service",
        "job_card_id",
        string="Repair Services",
        copy=True,
    )
    line_ids = fields.One2many(
        "workshop.job.card.line",
        "job_card_id",
        string="Repair Options",
        copy=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
        readonly=True,
    )
    selected_line_count = fields.Integer(
        compute="_compute_selected_line_count", string="Selected Line Count"
    )
    selected_total = fields.Monetary(
        related="total_amount",
        string="Legacy Selected Total",
        currency_field="currency_id",
        readonly=True,
    )
    total_amount = fields.Monetary(
        string="Total",
        compute="_compute_total_amount",
        store=True,
        currency_field="currency_id",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent", "Sent to Customer"),
            ("approved", "Approved"),
            ("repair_created", "Repair Order Created"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
        ],
        required=True,
        default="draft",
        copy=False,
        tracking=True,
        index=True,
    )
    approved_date = fields.Datetime(readonly=True, copy=False)
    approved_by = fields.Many2one(
        "res.users", string="Approved By", readonly=True, copy=False
    )
    repair_order_id = fields.Many2one(
        "repair.order",
        string="Repair Order",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )
    repair_order_count = fields.Integer(compute="_compute_repair_order_count")

    _sql_constraints = [
        (
            "workshop_job_card_name_unique",
            "unique(name)",
            "Job Card Number must be unique.",
        ),
        (
            "workshop_job_card_mileage_nonnegative",
            "check(mileage >= 0)",
            "Mileage cannot be negative.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            sequence_date = vals.get("job_card_date") or fields.Datetime.now()
            vals["name"] = self.env["ir.sequence"].with_context(
                ir_sequence_date=sequence_date
            ).next_by_code("workshop.job.card") or _("New")
            vals["state"] = "draft"
            if vals.get("vehicle_id") and "mileage" not in vals:
                vals["mileage"] = self.env["workshop.customer.vehicle"].browse(
                    vals["vehicle_id"]
                ).mileage
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if self._WORKFLOW_FIELDS.intersection(vals):
            raise UserError(_("Use the Job Card workflow buttons to change its status."))
        if self._CLOSED_READONLY_FIELDS.intersection(vals) and any(
            card.state in {"approved", "repair_created"} for card in self
        ):
            raise UserError(_("Approved Job Cards cannot be modified."))
        if vals.get("vehicle_id") and "mileage" not in vals:
            vals["mileage"] = self.env["workshop.customer.vehicle"].browse(
                vals["vehicle_id"]
            ).mileage
        return super().write(vals)

    @api.depends("customer_id.phone", "customer_id.mobile")
    def _compute_customer_phone(self):
        for card in self:
            card.customer_phone = card.customer_id.phone or card.customer_id.mobile

    @api.depends("repair_order_id")
    def _compute_repair_order_count(self):
        for card in self:
            card.repair_order_count = 1 if card.repair_order_id else 0

    @api.depends("line_ids.selected")
    def _compute_selected_line_count(self):
        for card in self:
            card.selected_line_count = len(card.line_ids.filtered("selected"))

    @api.depends("line_ids.selected", "line_ids.amount")
    def _compute_total_amount(self):
        for card in self:
            card.total_amount = sum(
                card.line_ids.filtered("selected").mapped("amount")
            )

    @api.onchange("customer_id")
    def _onchange_customer_id(self):
        if self.vehicle_id and self.vehicle_id.customer_id != self.customer_id:
            self.vehicle_id = False

    @api.onchange("vehicle_id")
    def _onchange_vehicle_id(self):
        if self.vehicle_id:
            self.mileage = self.vehicle_id.mileage

    @api.constrains("customer_id", "vehicle_id")
    def _check_vehicle_customer(self):
        for card in self:
            if card.vehicle_id and card.vehicle_id.customer_id != card.customer_id:
                raise ValidationError(
                    _("The selected vehicle does not belong to the selected customer.")
                )

    @api.constrains("mileage")
    def _check_mileage(self):
        if any(card.mileage < 0 for card in self):
            raise ValidationError(_("Mileage cannot be negative."))

    def _ensure_state(self, *allowed_states):
        self.ensure_one()
        if self.state not in allowed_states:
            raise UserError(_("This action is not available in the current state."))

    def _workflow_write(self, vals):
        return super(WorkshopJobCard, self).write(vals)

    def _services_without_single_selection(self):
        self.ensure_one()
        return self.service_line_ids.filtered(
            lambda service: len(service.option_line_ids.filtered("selected")) != 1
        )

    def _raise_for_incomplete_service_selections(self):
        self.ensure_one()
        incomplete_services = self._services_without_single_selection()
        if not incomplete_services:
            return
        service_names = "\n".join(
            "- %s" % service.repair_service_id.display_name
            for service in incomplete_services
        )
        raise ValidationError(
            _(
                "Please select one Product Option for the following "
                "Repair Services:\n%s"
            )
            % service_names
        )

    def action_send_to_customer(self):
        self._ensure_state("draft")
        if not self.customer_id or not self.vehicle_id or not self.technician_id:
            raise ValidationError(
                _("Customer, Vehicle, and Technician are required before sending.")
            )
        if not self.service_line_ids:
            raise ValidationError(
                _("Add at least one Repair Service before sending the Job Card.")
            )
        services_without_options = self.service_line_ids.filtered(
            lambda service: not service.option_line_ids
        )
        if services_without_options:
            service_names = "\n".join(
                "- %s" % service.repair_service_id.display_name
                for service in services_without_options
            )
            raise ValidationError(
                _(
                    "Add at least one Product Option for the following "
                    "Repair Services:\n%s"
                )
                % service_names
            )
        self._workflow_write({"state": "sent"})
        return True

    def action_approve(self):
        self._ensure_state("sent")
        if not self.line_ids.filtered("selected"):
            raise ValidationError(
                _("Select at least one Repair Option before approval.")
            )
        self._raise_for_incomplete_service_selections()
        self._workflow_write(
            {
                "state": "approved",
                "approved_date": fields.Datetime.now(),
                "approved_by": self.env.user.id,
            }
        )
        return True

    def action_reject(self):
        self._ensure_state("sent")
        self._workflow_write({"state": "rejected"})
        return True

    def action_cancel(self):
        self._ensure_state("draft", "sent", "approved")
        self._workflow_write({"state": "cancelled"})
        return True

    def action_reset_to_draft(self):
        self._ensure_state("rejected", "cancelled")
        self._workflow_write(
            {"state": "draft", "approved_date": False, "approved_by": False}
        )
        return True

    def action_create_repair_order(self):
        self.ensure_one()
        existing_repair = self.repair_order_id or self.env["repair.order"].search(
            [("job_card_id", "=", self.id)], limit=1
        )
        if existing_repair:
            raise UserError(_("A Repair Order already exists for this Job Card."))
        self._ensure_state("approved")

        selected_lines = self.service_line_ids.mapped("option_line_ids").filtered(
            "selected"
        )
        if not selected_lines:
            raise ValidationError(
                _("Select at least one Repair Option before creating a Repair Order.")
            )
        self._raise_for_incomplete_service_selections()

        repair = self.env["repair.order"].create(
            {
                "partner_id": self.customer_id.id,
                "schedule_date": self.job_card_date,
                "job_card_id": self.id,
                "customer_vehicle_id": self.vehicle_id.id,
            }
        )
        self.env["stock.move"].create(
            [
                {
                    "repair_id": repair.id,
                    "repair_line_type": "add",
                    "product_id": line.product_id.id,
                    "product_uom_qty": line.quantity,
                    "product_uom": line.product_uom_id.id,
                    "price_unit": line.unit_price,
                    "location_id": repair.location_id.id,
                    "location_dest_id": repair.location_dest_id.id,
                }
                for line in selected_lines
            ]
        )
        self._workflow_write(
            {"repair_order_id": repair.id, "state": "repair_created"}
        )
        return self.action_view_repair_order()

    def action_view_repair_order(self):
        self.ensure_one()
        if not self.repair_order_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Repair Order"),
            "res_model": "repair.order",
            "view_mode": "form",
            "res_id": self.repair_order_id.id,
        }
