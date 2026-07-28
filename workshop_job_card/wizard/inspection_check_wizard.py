from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class WorkshopInspectionCheckWizard(models.TransientModel):
    _name = "workshop.inspection.check.wizard"
    _description = "Workshop Inspection Check Wizard"

    job_card_id = fields.Many2one("workshop.job.card", required=True, readonly=True)
    repair_order_id = fields.Many2one("repair.order", readonly=True)
    inspection_type = fields.Selection(
        [
            ("customer_check", "Customer Check"),
            ("technician_inspection", "Technician Inspection"),
            ("delivery_inspection", "Delivery Check"),
        ],
        required=True,
        readonly=True,
    )
    template_id = fields.Many2one("workshop.inspection.template", required=True, readonly=True)
    inspector_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    inspection_date = fields.Datetime(required=True, default=fields.Datetime.now)
    line_ids = fields.One2many(
        "workshop.inspection.check.wizard.line",
        "wizard_id",
        string="Checkpoints",
    )
    general_remark = fields.Text()
    current_line_id = fields.Many2one(
        "workshop.inspection.check.wizard.line",
        string="Current Checkpoint",
        readonly=True,
    )
    current_checkpoint_number = fields.Integer(string="Current Sequence", compute="_compute_progress")
    total_checkpoint_count = fields.Integer(string="Total Checkpoints", compute="_compute_progress")
    progress_text = fields.Char(string="Progress", compute="_compute_progress")
    current_checkpoint_name = fields.Char(
        related="current_line_id.checkpoint_name",
        readonly=True,
    )
    current_checkpoint_description = fields.Text(
        related="current_line_id.description",
        readonly=True,
    )
    current_remark = fields.Char(string="Remark")
    yes_count = fields.Integer(compute="_compute_progress")
    no_count = fields.Integer(compute="_compute_progress")
    all_checkpoints_answered = fields.Boolean(compute="_compute_progress")
    can_go_previous = fields.Boolean(compute="_compute_progress")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for wizard in records:
            if not wizard.line_ids:
                wizard._load_template_lines()
            wizard._set_first_checkpoint()
        return records

    def _load_template_lines(self):
        """Create all transient answer lines before the modal is opened."""
        line_model = self.env["workshop.inspection.check.wizard.line"]
        for wizard in self:
            template_lines = wizard.template_id.line_ids.filtered("active").sorted(
                lambda line: (line.sequence, line.id)
            )
            if not template_lines:
                raise ValidationError(_("The selected inspection template has no active checkpoints."))
            line_model.create(
                [
                    {
                        "wizard_id": wizard.id,
                        "sequence": line.sequence,
                        "checkpoint_name": line.description,
                        "description": line.description,
                        "result": False,
                        "required": line.required,
                        "remark_required_when_no": line.remark_required_when_no,
                    }
                    for line in template_lines
                ]
            )

    def _set_first_checkpoint(self):
        self.ensure_one()
        first_line = self.line_ids.sorted(lambda line: (line.sequence, line.id))[:1]
        if not first_line:
            raise ValidationError(_("The inspection template has no active checkpoints."))
        self.current_line_id = first_line.id
        self.current_remark = first_line.remark or False

    @api.depends("line_ids.result", "line_ids.sequence", "current_line_id")
    def _compute_progress(self):
        for wizard in self:
            lines = wizard.line_ids.sorted(lambda line: (line.sequence, line.id))
            wizard.total_checkpoint_count = len(lines)
            wizard.current_checkpoint_number = (
                lines.ids.index(wizard.current_line_id.id) + 1
                if wizard.current_line_id and wizard.current_line_id.id in lines.ids
                else 0
            )
            wizard.yes_count = len(lines.filtered(lambda line: line.result == "yes"))
            wizard.no_count = len(lines.filtered(lambda line: line.result == "no"))
            answered_count = wizard.yes_count + wizard.no_count
            wizard.all_checkpoints_answered = bool(lines) and answered_count == len(lines)
            wizard.can_go_previous = wizard.current_checkpoint_number > 1
            wizard.progress_text = _("Checkpoint %(current)s of %(total)s") % (
                {
                    "current": wizard.current_checkpoint_number,
                    "total": len(lines),
                }
                if wizard.current_line_id
                else {
                    "current": 0,
                    "total": len(lines),
                }
            )

    def _reopen_same_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Inspection Check"),
            "res_model": self._name,
            "view_mode": "form",
            "view_id": self.env.ref("workshop_job_card.view_workshop_inspection_check_wizard_form").id,
            "res_id": self.id,
            "target": "new",
        }

    def _save_current_answer(self, result):
        self.ensure_one()
        if not self.current_line_id:
            raise UserError(_("There is no current checkpoint to answer."))
        if result == "no" and self.current_line_id.remark_required_when_no and not self.current_remark:
            raise ValidationError(_("Please enter a remark before marking this checkpoint as No."))
        self.current_line_id.write(
            {
                "result": result,
                "remark": self.current_remark,
            }
        )

    def _move_next_or_complete(self):
        self.ensure_one()
        ordered_lines = self.line_ids.sorted(lambda line: (line.sequence, line.id))
        if not ordered_lines:
            raise ValidationError(_("No inspection checkpoints were found."))
        current_index = ordered_lines.ids.index(self.current_line_id.id)
        if current_index + 1 < len(ordered_lines):
            next_line = ordered_lines[current_index + 1]
            self.current_line_id = next_line.id
            self.current_remark = next_line.remark or False
            return self._reopen_same_wizard()
        return self._finalize_and_close()

    def _answer_current_checkpoint(self, result):
        self.ensure_one()
        self._save_current_answer(result)
        return self._move_next_or_complete()

    def action_answer_yes(self):
        return self._answer_current_checkpoint("yes")

    def action_answer_no(self):
        return self._answer_current_checkpoint("no")

    def action_previous_checkpoint(self):
        self.ensure_one()
        if self.current_line_id:
            self.current_line_id.remark = self.current_remark
        ordered_lines = self.line_ids.sorted(lambda line: (line.sequence, line.id))
        if self.current_line_id and self.current_line_id.id in ordered_lines.ids:
            current_index = ordered_lines.ids.index(self.current_line_id.id)
            if current_index > 0:
                previous_line = ordered_lines[current_index - 1]
                self.current_line_id = previous_line.id
                self.current_remark = previous_line.remark or False
        return self._reopen_same_wizard()

    def _validate_complete(self):
        for wizard in self:
            if not wizard.inspector_id:
                raise ValidationError(_("Inspector is required."))
            if not wizard.job_card_id:
                raise ValidationError(_("A valid Job Card is required."))
            if not wizard.line_ids:
                raise ValidationError(_("No inspection checkpoints were found."))
            completed = wizard.job_card_id.inspection_ids.filtered(
                lambda inspection: inspection.inspection_type == wizard.inspection_type
                and inspection.state == "completed"
            )
            if completed:
                raise UserError(_("This inspection has already been completed for the Job Card."))
            missing_results = wizard.line_ids.filtered(lambda line: not line.result)
            if missing_results:
                raise ValidationError(_("Every checkpoint must have a Yes or No result."))
            missing_remarks = wizard.line_ids.filtered(
                lambda line: line.result == "no"
                and line.remark_required_when_no
                and not line.remark
            )
            if missing_remarks:
                raise ValidationError(_("Please enter a remark for checkpoints marked No."))

    def _finalize_inspection(self):
        self.ensure_one()
        self._validate_complete()
        creation_source = "repair_order_button" if self.repair_order_id else "job_card_button"
        inspection = self.env["workshop.job.card.inspection"].with_context(
            allow_inspection_history_create=True,
            inspection_creation_source=creation_source,
        ).create(
            {
                "job_card_id": self.job_card_id.id,
                "repair_order_id": self.repair_order_id.id or False,
                "inspection_type": self.inspection_type,
                "template_id": self.template_id.id,
                "inspector_id": self.inspector_id.id,
                "inspection_date": self.inspection_date,
                "completed_date": fields.Datetime.now(),
                "completed_by": self.env.user.id,
                "state": "completed",
                "general_remark": self.general_remark,
                "creation_source": creation_source,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "sequence": line.sequence,
                            "description": line.checkpoint_name,
                            "checkpoint_name": line.checkpoint_name,
                            "result": line.result,
                            "remark": line.remark,
                        },
                    )
                    for line in self.line_ids
                ],
            }
        )
        inspection.message_post(body=_("Inspection history created from check wizard."))

    def _finalize_and_close(self):
        self.ensure_one()
        self._finalize_inspection()
        self.current_line_id = False
        self.current_remark = False
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_complete_check(self):
        return self._finalize_and_close()


class WorkshopInspectionCheckWizardLine(models.TransientModel):
    _name = "workshop.inspection.check.wizard.line"
    _description = "Workshop Inspection Check Wizard Line"
    _order = "sequence, id"

    wizard_id = fields.Many2one(
        "workshop.inspection.check.wizard",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    checkpoint_name = fields.Char(required=True, readonly=True)
    result = fields.Selection(
        [
            ("yes", "Yes"),
            ("no", "No"),
        ],
        string="Result",
    )
    description = fields.Text(readonly=True)
    remark = fields.Char()
    required = fields.Boolean(readonly=True)
    remark_required_when_no = fields.Boolean(readonly=True)
    is_answered = fields.Boolean(compute="_compute_is_answered", store=True)

    @api.depends("result")
    def _compute_is_answered(self):
        for line in self:
            line.is_answered = line.result in ("yes", "no")
