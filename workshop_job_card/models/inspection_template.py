from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class WorkshopInspectionTemplate(models.Model):
    _name = "workshop.inspection.template"
    _description = "Workshop Inspection Template"
    _order = "sequence, name, id"
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    inspection_type = fields.Selection(
        [
            ("customer_check", "Customer Vehicle Condition Check"),
            ("technician_inspection", "Technician Inspection"),
            ("delivery_inspection", "Delivery Inspection"),
        ],
        required=True,
        index=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    sequence = fields.Integer(default=10)
    line_ids = fields.One2many(
        "workshop.inspection.template.line",
        "template_id",
        string="Checklist",
        copy=True,
    )

class WorkshopInspectionTemplateLine(models.Model):
    _name = "workshop.inspection.template.line"
    _description = "Workshop Inspection Template Line"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "workshop.inspection.template",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    description = fields.Char(required=True)
    name = fields.Char(string="Checkpoint", related="description", readonly=False)
    result_type_id = fields.Many2one(
        "workshop.inspection.result.type",
        string="Result Type",
        default=lambda self: self._default_result_type_id(),
        required=True,
        ondelete="restrict",
    )
    default_result_option_id = fields.Many2one(
        "workshop.inspection.result.option",
        string="Default Result",
        domain="[('result_type_id', '=', result_type_id), ('active', '=', True)]",
        ondelete="restrict",
    )
    required = fields.Boolean(default=True)
    photo_required = fields.Boolean(string="Photo Required", default=False)
    allow_multiple_photos = fields.Boolean(string="Allow Multiple Photos", default=True)
    active = fields.Boolean(default=True)

    def _default_result_type_id(self):
        result_type = self.env.ref(
            "workshop_job_card.inspection_result_type_yes_no",
            raise_if_not_found=False,
        )
        if not result_type:
            result_type = self.env["workshop.inspection.result.type"].search(
                [("code", "=", "yes_no")],
                limit=1,
            )
        return result_type.id if result_type else False

    @api.onchange("result_type_id")
    def _onchange_result_type_id(self):
        if self.default_result_option_id.result_type_id != self.result_type_id:
            self.default_result_option_id = False

    @api.constrains("result_type_id", "default_result_option_id")
    def _check_default_option_matches_type(self):
        for line in self:
            if (
                line.default_result_option_id
                and line.default_result_option_id.result_type_id != line.result_type_id
            ):
                raise ValidationError(_("Default Result must belong to the selected Result Type."))

    def init(self):
        self.env.cr.execute(
            """
            UPDATE workshop_inspection_template_line
               SET allow_multiple_photos = TRUE
             WHERE allow_multiple_photos IS NULL
            """
        )
