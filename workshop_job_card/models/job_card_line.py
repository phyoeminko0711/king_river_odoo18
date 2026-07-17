from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class WorkshopJobCardLine(models.Model):
    _name = "workshop.job.card.line"
    _description = "Workshop Job Card Repair Option"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    job_card_id = fields.Many2one(
        "workshop.job.card", required=True, ondelete="cascade", index=True
    )
    repair_service = fields.Char(string="Repair Service", required=True, index=True)
    product_id = fields.Many2one(
        "product.product",
        string="Part / Option",
        required=True,
        ondelete="restrict",
        domain=[("type", "=", "consu")],
    )
    brand_id = fields.Many2one(
        related="product_id.brand_id", store=True, readonly=True
    )
    part_number = fields.Char(
        related="product_id.default_code",
        string="Part No.",
        store=True,
        readonly=True,
    )
    warranty = fields.Char()
    quantity = fields.Float(
        required=True, default=1.0, digits="Product Unit of Measure"
    )
    product_uom_id = fields.Many2one(
        "uom.uom", string="UoM", required=True, ondelete="restrict"
    )
    unit_price = fields.Monetary(required=True, default=0.0)
    amount = fields.Monetary(compute="_compute_amount", store=True, readonly=True)
    selected = fields.Boolean(string="Selected")
    currency_id = fields.Many2one(
        related="job_card_id.currency_id", store=True, readonly=True
    )

    _sql_constraints = [
        (
            "workshop_job_card_line_quantity_positive",
            "check(quantity > 0)",
            "Option quantity must be greater than zero.",
        ),
        (
            "workshop_job_card_line_price_nonnegative",
            "check(unit_price >= 0)",
            "Unit price cannot be negative.",
        ),
    ]

    @api.depends("quantity", "unit_price")
    def _compute_amount(self):
        for line in self:
            line.amount = line.quantity * line.unit_price

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id
            self.unit_price = self.product_id.lst_price

    @api.onchange("selected", "repair_service")
    def _onchange_selected(self):
        for line in self.filtered(lambda item: item.selected and item.repair_service):
            for sibling in line.job_card_id.line_ids:
                if (
                    sibling != line
                    and sibling.selected
                    and sibling.repair_service == line.repair_service
                ):
                    sibling.selected = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._normalize_repair_service(vals)
            card = self.env["workshop.job.card"].browse(vals.get("job_card_id"))
            if (
                card
                and card.state != "draft"
                and not self.env.context.get("skip_job_card_state_check")
            ):
                raise UserError(_("Repair Options can only be added in Draft."))
            product = self.env["product.product"].browse(vals.get("product_id"))
            if product:
                vals.setdefault("product_uom_id", product.uom_id.id)
                vals.setdefault("unit_price", product.lst_price)
        lines = super().create(vals_list)
        lines.filtered("selected")._unselect_competing_lines()
        return lines

    def write(self, vals):
        vals = dict(vals)
        self._normalize_repair_service(vals)
        business_fields = {
            "sequence",
            "job_card_id",
            "repair_service",
            "product_id",
            "warranty",
            "quantity",
            "product_uom_id",
            "unit_price",
            "selected",
        }.intersection(vals)
        for line in self:
            if line.job_card_id.state == "sent" and business_fields - {"selected"}:
                raise UserError(_("Only option selection can change after sending."))
            if line.job_card_id.state not in {"draft", "sent"} and business_fields:
                raise UserError(_("Approved or closed Repair Options cannot be modified."))
        result = super().write(vals)
        if vals.get("selected") or ("repair_service" in vals and any(self.mapped("selected"))):
            self.filtered("selected")._unselect_competing_lines()
        return result

    def unlink(self):
        if any(line.job_card_id.state != "draft" for line in self):
            raise UserError(_("Repair Options can only be deleted in Draft."))
        return super().unlink()

    def _unselect_competing_lines(self):
        for line in self:
            if not line.selected:
                continue
            competitors = self.search(
                [
                    ("job_card_id", "=", line.job_card_id.id),
                    ("repair_service", "=", line.repair_service),
                    ("selected", "=", True),
                    ("id", "!=", line.id),
                ]
            )
            if competitors:
                competitors.with_context(skip_selection_sync=True).write(
                    {"selected": False}
                )

    @staticmethod
    def _normalize_repair_service(vals):
        value = vals.get("repair_service")
        if isinstance(value, str):
            vals["repair_service"] = value.strip()

    @api.constrains("quantity", "unit_price", "product_id", "product_uom_id")
    def _check_line_values(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_("Option quantity must be greater than zero."))
            if line.unit_price < 0:
                raise ValidationError(_("Unit price cannot be negative."))
            if (
                line.product_id
                and line.product_uom_id
                and line.product_uom_id.category_id != line.product_id.uom_id.category_id
            ):
                raise ValidationError(
                    _("The option UoM must use the product's UoM category.")
                )
