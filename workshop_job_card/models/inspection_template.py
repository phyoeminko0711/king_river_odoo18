from odoo import fields, models


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
    default_result = fields.Selection(
        [
            ("yes", "Yes"),
            ("no", "No"),
        ],
        default="yes",
        required=True,
    )
    required = fields.Boolean(default=True)
    remark_required = fields.Boolean(string="Remark Required When No")
    remark_required_when_no = fields.Boolean(
        string="Remark Required When No",
        related="remark_required",
        readonly=False,
    )
    active = fields.Boolean(default=True)

    def init(self):
        self.env.cr.execute(
            """
            UPDATE workshop_inspection_template_line
               SET default_result = CASE
                   WHEN default_result = 'ok' THEN 'yes'
                   WHEN default_result IN ('ng', 'na') THEN 'no'
                   ELSE default_result
               END
             WHERE default_result IN ('ok', 'ng', 'na')
            """
        )
