from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class WorkshopInspectionResultType(models.Model):
    _name = "workshop.inspection.result.type"
    _description = "Workshop Inspection Result Type"
    _order = "sequence, name, id"
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, index=True)
    option_ids = fields.One2many(
        "workshop.inspection.result.option",
        "result_type_id",
        string="Options",
        copy=True,
    )

    _sql_constraints = [
        (
            "workshop_inspection_result_type_code_unique",
            "unique(code, company_id)",
            "Result Type code must be unique per company.",
        ),
    ]

    @api.constrains("option_ids")
    def _check_has_active_options(self):
        for result_type in self:
            if result_type.active and result_type.option_ids and not result_type.option_ids.filtered("active"):
                raise ValidationError(_("An active Result Type must have at least one active option."))


class WorkshopInspectionResultOption(models.Model):
    _name = "workshop.inspection.result.option"
    _description = "Workshop Inspection Result Option"
    _order = "result_type_id, sequence, name, id"
    _check_company_auto = True

    result_type_id = fields.Many2one(
        "workshop.inspection.result.type",
        required=True,
        ondelete="cascade",
        index=True,
    )
    name = fields.Char(required=True, index=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(related="result_type_id.company_id", store=True, readonly=True)
    is_positive = fields.Boolean(default=True)
    requires_remark = fields.Boolean()
    color = fields.Integer()
    icon = fields.Char()

    _sql_constraints = [
        (
            "workshop_inspection_result_option_code_unique",
            "unique(result_type_id, code)",
            "Result Option code must be unique per Result Type.",
        ),
    ]
