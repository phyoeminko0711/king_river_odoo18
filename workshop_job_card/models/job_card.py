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
        "testing_driver_id",
        "assistant_technician_id",
        "complaint",
        "diagnosis",
        "recommendation",
        "service_line_ids",
        "line_ids",
        "labour_cost",
        "service_cost",
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
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
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
        string="Product Lines",
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
    labour_cost = fields.Monetary(
        string="Labour Cost",
        default=0.0,
        currency_field="currency_id",
        tracking=True,
    )
    service_cost = fields.Monetary(
        string="Service Cost",
        default=0.0,
        currency_field="currency_id",
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent", "Sent to Customer"),
            ("approved", "Approved"),
            ("repair_created", "Repair Order Created"),
            ("repair_completed", "Repair Completed"),
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
    inspection_ids = fields.One2many(
        "workshop.job.card.inspection",
        "job_card_id",
        string="Inspection History",
    )
    customer_check_state = fields.Selection(
        compute="_compute_inspection_status",
        selection=[
            ("none", "Not Started"),
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        string="Customer Check",
    )
    customer_check_completed = fields.Boolean(compute="_compute_inspection_status")
    customer_check_in_progress = fields.Boolean(compute="_compute_inspection_status")
    technician_inspection_state = fields.Selection(
        compute="_compute_inspection_status",
        selection=[
            ("none", "Not Started"),
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        string="Technician Inspection",
    )
    technician_inspection_completed = fields.Boolean(compute="_compute_inspection_status")
    technician_inspection_in_progress = fields.Boolean(compute="_compute_inspection_status")
    delivery_inspection_completed = fields.Boolean(compute="_compute_inspection_status")

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

    def init(self):
        self.env.cr.execute(
            """
            UPDATE workshop_job_card
               SET state = 'draft'
             WHERE state IN ('customer_check', 'technician_inspection')
            """
        )

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
            card.state in {"approved", "repair_created", "repair_completed"} for card in self
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

    @api.depends("inspection_ids.state", "inspection_ids.inspection_type", "inspection_ids.inspection_date")
    def _compute_inspection_status(self):
        for card in self:
            customer_check = card._get_latest_inspection("customer_check")
            technician_inspection = card._get_latest_inspection("technician_inspection")
            card.customer_check_state = customer_check.state if customer_check else "none"
            card.technician_inspection_state = technician_inspection.state if technician_inspection else "none"
            card.customer_check_completed = card._has_completed_inspection("customer_check")
            card.technician_inspection_completed = card._has_completed_inspection("technician_inspection")
            card.delivery_inspection_completed = card._has_completed_inspection("delivery_inspection")
            card.customer_check_in_progress = bool(
                card.inspection_ids.filtered(
                    lambda inspection: inspection.inspection_type == "customer_check"
                    and inspection.state in ("draft", "in_progress")
                )
            )
            card.technician_inspection_in_progress = bool(
                card.inspection_ids.filtered(
                    lambda inspection: inspection.inspection_type == "technician_inspection"
                    and inspection.state in ("draft", "in_progress")
                )
            )

    @api.depends("line_ids.selected")
    def _compute_selected_line_count(self):
        for card in self:
            card.selected_line_count = len(card.line_ids.filtered("selected"))

    @api.depends("line_ids.amount", "labour_cost", "service_cost")
    def _compute_total_amount(self):
        for card in self:
            card.total_amount = (
                sum(card.line_ids.mapped("amount"))
                + card.labour_cost
                + card.service_cost
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

    @api.constrains("labour_cost", "service_cost")
    def _check_service_amounts(self):
        for card in self:
            if card.labour_cost < 0:
                raise ValidationError(_("Labour Cost must be greater than or equal to zero."))
            if card.service_cost < 0:
                raise ValidationError(_("Service Cost must be greater than or equal to zero."))

    @api.constrains("technician_id", "assistant_technician_id", "testing_driver_id")
    def _check_unique_employee_roles(self):
        for card in self:
            employees = (
                card.technician_id
                | card.assistant_technician_id
                | card.testing_driver_id
            )
            selected_count = sum(
                bool(employee)
                for employee in (
                    card.technician_id,
                    card.assistant_technician_id,
                    card.testing_driver_id,
                )
            )
            if len(employees) != selected_count:
                raise ValidationError(
                    _("Technician, Assistant Technician, and Testing Driver must be different employees.")
                )

    def _ensure_state(self, *allowed_states):
        self.ensure_one()
        if self.state not in allowed_states:
            raise UserError(_("This action is not available in the current state."))

    def _workflow_write(self, vals):
        return super(WorkshopJobCard, self).write(vals)

    def _get_latest_inspection(self, inspection_type):
        self.ensure_one()
        return self.inspection_ids.filtered(
            lambda inspection: inspection.inspection_type == inspection_type
        ).sorted(lambda inspection: (inspection.inspection_date, inspection.id), reverse=True)[:1]

    def _has_completed_inspection(self, inspection_type):
        self.ensure_one()
        return bool(
            self.inspection_ids.filtered(
                lambda inspection: inspection.inspection_type == inspection_type
                and inspection.state == "completed"
            )
        )

    def _get_default_inspection_template(self, inspection_type):
        self.ensure_one()
        template = self.env["workshop.inspection.template"].search(
            [
                ("inspection_type", "=", inspection_type),
                ("active", "=", True),
                ("company_id", "=", self.company_id.id),
            ],
            order="sequence, id",
            limit=1,
        )
        if not template:
            raise ValidationError(
                _("Please configure an active %s inspection template first.")
                % dict(self.env["workshop.inspection.template"]._fields["inspection_type"].selection)[inspection_type]
            )
        return template

    def _open_or_create_inspection(self, inspection_type, repair_order=False):
        self.ensure_one()
        inspection = self.inspection_ids.filtered(
            lambda record: record.inspection_type == inspection_type and record.state == "completed"
        )[:1]
        if inspection:
            return {
                "type": "ir.actions.act_window",
                "name": inspection.display_name,
                "res_model": "workshop.job.card.inspection",
                "view_mode": "form",
                "res_id": inspection.id,
                "target": "current",
            }
        template = self._get_default_inspection_template(inspection_type)
        inspector = self.env.user
        if inspection_type == "technician_inspection" and self.technician_id.user_id:
            inspector = self.technician_id.user_id
        wizard = self.env["workshop.inspection.check.wizard"].create(
            {
                "job_card_id": self.id,
                "repair_order_id": repair_order.id if repair_order else False,
                "inspection_type": inspection_type,
                "template_id": template.id,
                "inspector_id": inspector.id,
                "inspection_date": fields.Datetime.now(),
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Inspection Check"),
            "res_model": "workshop.inspection.check.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("workshop_job_card.view_workshop_inspection_check_wizard_form").id,
            "res_id": wizard.id,
            "target": "new",
        }

    def action_customer_check(self):
        self.ensure_one()
        self._ensure_state("draft")
        return self._open_or_create_inspection("customer_check")

    def action_technician_inspection(self):
        self.ensure_one()
        if not self._has_completed_inspection("customer_check"):
            raise ValidationError(_("Complete the Customer Vehicle Condition Check before Technician Inspection."))
        self._ensure_state("draft")
        return self._open_or_create_inspection("technician_inspection")

    def _sync_inspection_workflow_state(self):
        return True

    def action_open_add_repair_service_wizard(self):
        self._ensure_state("draft", "sent")
        action = self.env["ir.actions.actions"]._for_xml_id(
            "workshop_job_card.action_add_repair_service_wizard"
        )
        action["context"] = {
            **self.env.context,
            "default_job_card_id": self.id,
        }
        return action

    def action_open_remove_repair_service_wizard(self):
        self.ensure_one()
        if self.state not in {"draft", "sent"}:
            raise UserError(
                _(
                    "Repair Services can only be removed while the Job Card is "
                    "before customer approval."
                )
            )
        action = self.env["ir.actions.actions"]._for_xml_id(
            "workshop_job_card.action_remove_repair_service_wizard"
        )
        action["context"] = {
            **self.env.context,
            "default_job_card_id": self.id,
        }
        return action

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

    def _get_single_repair_charge_product(self, flag_field):
        self.ensure_one()
        product_domain = [
            ("active", "=", True),
            ("product_tmpl_id.active", "=", True),
            ("type", "=", "service"),
            ("product_tmpl_id.%s" % flag_field, "=", True),
        ]
        products = self.env["product.product"].search(product_domain)
        if flag_field == "is_labour_cost":
            if not products:
                raise ValidationError(_("No Labour Cost service product is configured."))
            if len(products) > 1:
                raise ValidationError(_("Only one active Labour Cost service product may be configured."))
        else:
            if not products:
                raise ValidationError(_("No Workshop Service Product is configured."))
            if len(products) > 1:
                raise ValidationError(_("Only one active Workshop Service Product may be configured."))
        return products

    def _prepare_repair_charge_line_vals(self, repair, product, amount, charge_type, sequence):
        self.ensure_one()
        return {
            "sequence": sequence,
            "repair_id": repair.id,
            "charge_type": charge_type,
            "product_id": product.id,
            "product_uom_qty": 1.0,
            "product_uom_id": product.uom_id.id,
            "price_unit": amount,
        }

    def _prepare_service_product_charge_line_vals(self, repair, line, sequence):
        self.ensure_one()
        return {
            "sequence": sequence,
            "repair_id": repair.id,
            "charge_type": "service",
            "product_id": line.product_id.id,
            "product_uom_qty": line.quantity,
            "product_uom_id": line.product_uom_id.id,
            "price_unit": line.unit_price,
        }

    def _prepare_repair_charge_lines(self, repair):
        self.ensure_one()
        charge_vals = []
        if self.labour_cost > 0:
            labour_product = self._get_single_repair_charge_product("is_labour_cost")
            charge_vals.append(
                self._prepare_repair_charge_line_vals(
                    repair, labour_product, self.labour_cost, "labour", 10
                )
            )
        if self.service_cost > 0:
            service_product = self._get_single_repair_charge_product("is_workshop_service")
            charge_vals.append(
                self._prepare_repair_charge_line_vals(
                    repair, service_product, self.service_cost, "service", 20
                )
            )
        return charge_vals

    def action_send_to_customer(self):
        self._ensure_state("draft")
        if not (
            self._has_completed_inspection("customer_check")
            and self._has_completed_inspection("technician_inspection")
        ):
            raise ValidationError(_("Complete the Customer Check and Technician Inspection before sending the Job Card to the customer."))
        if not self.customer_id or not self.vehicle_id or not self.technician_id:
            raise ValidationError(
                _("Customer, Vehicle, and Technician are required before sending.")
            )
        if not self.line_ids:
            raise ValidationError(_("Add at least one product line before sending the Job Card."))
        self._workflow_write({"state": "sent"})
        return True

    def action_approve(self):
        self._ensure_state("sent")
        if not self.line_ids:
            raise ValidationError(_("Add at least one product line before approval."))
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

        product_lines = self.line_ids.filtered("product_id")
        if not product_lines:
            raise ValidationError(_("Add at least one product line before creating a Repair Order."))

        repair = self.env["repair.order"].create(
            {
                "partner_id": self.customer_id.id,
                "schedule_date": self.job_card_date,
                "job_card_id": self.id,
                "customer_vehicle_id": self.vehicle_id.id,
                "technician_id": self.technician_id.id,
                "testing_driver_id": self.testing_driver_id.id,
                "assistant_technician_id": self.assistant_technician_id.id,
            }
        )
        part_lines = product_lines.filtered(lambda line: line.product_id.type != "service")
        if part_lines:
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
                    for line in part_lines
                ]
            )
        charge_vals = self._prepare_repair_charge_lines(repair)
        service_lines = product_lines.filtered(lambda line: line.product_id.type == "service")
        charge_vals.extend(
            self._prepare_service_product_charge_line_vals(repair, line, 100 + index)
            for index, line in enumerate(service_lines, start=1)
        )
        if charge_vals:
            self.env["workshop.repair.charge.line"].create(charge_vals)
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
