from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class WorkshopJobCardInspection(models.Model):
    _name = "workshop.job.card.inspection"
    _description = "Workshop Job Card Inspection"
    _inherit = ["mail.thread"]
    _order = "inspection_date desc, id desc"
    _rec_name = "name"
    _check_company_auto = True

    name = fields.Char(compute="_compute_name", store=True)
    job_card_id = fields.Many2one(
        "workshop.job.card",
        string="Job Card",
        required=True,
        ondelete="restrict",
        index=True,
    )
    repair_order_id = fields.Many2one(
        "repair.order",
        string="Repair Order",
        readonly=True,
        copy=False,
        ondelete="restrict",
        index=True,
    )
    company_id = fields.Many2one(
        related="job_card_id.company_id",
        store=True,
        readonly=True,
    )
    inspection_type = fields.Selection(
        [
            ("customer_check", "Customer Vehicle Condition Check"),
            ("technician_inspection", "Technician Inspection"),
            ("delivery_inspection", "Delivery Inspection"),
        ],
        required=True,
        index=True,
        tracking=True,
    )
    template_id = fields.Many2one(
        "workshop.inspection.template",
        string="Template",
        required=True,
        ondelete="restrict",
        check_company=True,
    )
    inspector_id = fields.Many2one(
        "res.users",
        string="Inspector",
        default=lambda self: self.env.user,
        required=True,
        tracking=True,
    )
    inspection_date = fields.Datetime(
        string="Inspection Date",
        default=fields.Datetime.now,
        required=True,
        tracking=True,
    )
    completed_date = fields.Datetime(string="Completed Date", readonly=True, copy=False)
    completed_by = fields.Many2one("res.users", string="Completed By", readonly=True, copy=False)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    general_remark = fields.Text()
    remarks = fields.Text(related="general_remark", readonly=False)
    creation_source = fields.Selection(
        [
            ("job_card_button", "Job Card Button"),
            ("repair_order_button", "Repair Order Button"),
        ],
        required=True,
        readonly=True,
        copy=False,
    )
    completed_by_id = fields.Many2one(related="completed_by", string="Completed By", readonly=True)
    completion_date = fields.Datetime(related="completed_date", string="Completion Date", readonly=True)
    line_ids = fields.One2many(
        "workshop.job.card.inspection.line",
        "inspection_id",
        string="Inspection Lines",
        copy=True,
    )

    @api.depends("job_card_id.name", "inspection_type")
    def _compute_name(self):
        labels = dict(self._fields["inspection_type"].selection)
        for inspection in self:
            inspection.name = "%s - %s" % (
                inspection.job_card_id.name or _("Job Card"),
                labels.get(inspection.inspection_type, _("Inspection")),
            )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("allow_inspection_history_create"):
            raise UserError(_("Inspection history can only be created through the Job Card or Repair Order check workflow."))
        for vals in vals_list:
            vals.setdefault("creation_source", self.env.context.get("inspection_creation_source"))
        records = super().create(vals_list)
        for inspection in records:
            if not inspection.line_ids:
                inspection._copy_template_lines()
        return records

    def write(self, vals):
        if self.env.context.get("skip_inspection_write_protection"):
            return super().write(vals)
        if vals.get("state") == "completed":
            raise UserError(_("Use the Complete button to complete an inspection."))
        protected_fields = {
            "job_card_id",
            "inspection_type",
            "template_id",
            "creation_source",
            "completed_date",
            "completed_by",
        }
        if protected_fields.intersection(vals):
            raise ValidationError(_("Job Card, Inspection Type, Template, and Creation Source cannot be changed after creation."))
        if any(record.state == "completed" for record in self) and set(vals) - {
            "message_follower_ids",
            "message_partner_ids",
        }:
            raise ValidationError(_("Completed inspections cannot be modified. Create a new inspection if needed."))
        return super().write(vals)

    @api.constrains("job_card_id", "inspection_type", "state")
    def _check_unique_inspection_per_phase(self):
        for inspection in self:
            if inspection.state in ("draft", "in_progress"):
                duplicate = self.search(
                    [
                        ("id", "!=", inspection.id),
                        ("job_card_id", "=", inspection.job_card_id.id),
                        ("inspection_type", "=", inspection.inspection_type),
                        ("state", "in", ["draft", "in_progress"]),
                    ],
                    limit=1,
                )
                if duplicate:
                    raise ValidationError(_("Only one open inspection is allowed per inspection type for a Job Card."))
            if inspection.state == "completed":
                completed_duplicate = self.search(
                    [
                        ("id", "!=", inspection.id),
                        ("job_card_id", "=", inspection.job_card_id.id),
                        ("inspection_type", "=", inspection.inspection_type),
                        ("state", "=", "completed"),
                    ],
                    limit=1,
                )
                if completed_duplicate:
                    raise ValidationError(_("Only one completed inspection is allowed per inspection type for this phase."))

    def unlink(self):
        if not self.env.context.get("allow_inspection_unlink"):
            raise ValidationError(_("Inspection history cannot be deleted."))
        return super().unlink()

    def copy(self, default=None):
        raise ValidationError(_("Inspection history cannot be duplicated."))

    def _copy_template_lines(self):
        for inspection in self:
            template_lines = inspection.template_id.line_ids.filtered("active")
            line_commands = []
            for line in template_lines:
                option = line.default_result_option_id or line.result_type_id.option_ids.filtered("active")[:1]
                if not option:
                    continue
                line_commands.append(
                    (
                        0,
                        0,
                        {
                            "sequence": line.sequence,
                            "description": line.description,
                            "checkpoint_name": line.description,
                            "result_option_id": option.id,
                            "result_name": option.name,
                            "required": line.required,
                            "remark_required": option.requires_remark,
                        },
                    )
                )
            inspection.line_ids = line_commands

    def _validate_before_complete(self):
        for inspection in self:
            if not inspection.inspector_id:
                raise ValidationError(_("Inspector is required before completing the inspection."))
            missing_required = inspection.line_ids.filtered(lambda line: line.required and not line.result_name)
            if missing_required:
                raise ValidationError(_("All required inspection lines must have a result before completion."))
            missing_remarks = inspection.line_ids.filtered(lambda line: line.remark_required and not line.remark)
            if missing_remarks:
                raise ValidationError(_("Remarks are required for some inspection lines before completion."))

    def action_complete(self):
        for inspection in self:
            if inspection.state not in ("draft", "in_progress"):
                raise ValidationError(_("Only draft or in-progress inspections can be completed."))
            inspection._validate_before_complete()
            inspection.with_context(skip_inspection_write_protection=True).write(
                {
                    "state": "completed",
                    "completed_date": fields.Datetime.now(),
                    "completed_by": self.env.user.id,
                }
            )
            inspection.job_card_id._sync_inspection_workflow_state()
            inspection.message_post(body=_("Inspection completed."))
        return True

    def action_cancel(self):
        self.filtered(lambda inspection: inspection.state in ("draft", "in_progress")).write({"state": "cancelled"})
        return True


class WorkshopJobCardInspectionLine(models.Model):
    _name = "workshop.job.card.inspection.line"
    _description = "Workshop Job Card Inspection Line"
    _order = "sequence, id"

    inspection_id = fields.Many2one(
        "workshop.job.card.inspection",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    description = fields.Char(required=True)
    checkpoint_name = fields.Char(string="Checkpoint", related="description", readonly=False)
    result_option_id = fields.Many2one(
        "workshop.inspection.result.option",
        string="Result Option",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )
    result_name = fields.Char(
        string="Result",
        required=True,
        copy=False,
    )
    result = fields.Char(string="Result", related="result_name", readonly=True)
    result_is_positive = fields.Boolean(related="result_option_id.is_positive", readonly=True)
    remark = fields.Char()
    required = fields.Boolean(readonly=True)
    remark_required = fields.Boolean(readonly=True)

    def init(self):
        self.env.cr.execute(
            """
            UPDATE workshop_job_card_inspection_line
               SET result_name = COALESCE(result_name, result)
             WHERE result_name IS NULL
               AND result IS NOT NULL
            """
        )

    def write(self, vals):
        if self.env.context.get("skip_inspection_write_protection"):
            return super().write(vals)
        protected_fields = {
            "inspection_id",
            "sequence",
            "description",
            "checkpoint_name",
            "required",
            "remark_required",
        }
        # if protected_fields.intersection(vals):
        #     raise ValidationError(_("Copied inspection checklist details cannot be modified."))
        # if any(line.inspection_id.state == "completed" for line in self):
        #     raise ValidationError(_("Completed inspection lines cannot be modified."))
        return super().write(vals)

    def unlink(self):
        if any(line.inspection_id.state == "completed" for line in self):
            raise ValidationError(_("Completed inspection lines cannot be deleted."))
        return super().unlink()
