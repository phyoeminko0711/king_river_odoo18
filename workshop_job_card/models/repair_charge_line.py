from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class WorkshopRepairChargeLine(models.Model):
    _name = "workshop.repair.charge.line"
    _description = "Workshop Repair Service Charge"
    _order = "sequence, id"
    _check_company_auto = True

    sequence = fields.Integer(default=10)
    repair_id = fields.Many2one(
        "repair.order",
        string="Repair Order",
        required=True,
        ondelete="cascade",
        index=True,
        check_company=True,
    )
    company_id = fields.Many2one(
        related="repair_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related="repair_id.company_id.currency_id",
        store=True,
        readonly=True,
    )
    charge_type = fields.Selection(
        [
            ("labour", "Labour Cost"),
            ("service", "Service Cost"),
        ],
        required=True,
        default="service",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        ondelete="restrict",
        check_company=True,
        domain="[('type', '=', 'service')]",
    )
    product_uom_qty = fields.Float(string="Quantity", required=True, default=1.0)
    product_uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        required=True,
    )
    price_unit = fields.Monetary(
        string="Unit Price",
        required=True,
        currency_field="currency_id",
    )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id

    @api.constrains("product_id")
    def _check_service_product(self):
        for line in self:
            if line.product_id and line.product_id.type != "service":
                raise ValidationError(
                    _("Repair service charge products must be Service products.")
                )

    @api.constrains("product_uom_qty", "price_unit")
    def _check_positive_values(self):
        for line in self:
            if line.product_uom_id and float_compare(
                line.product_uom_qty,
                0.0,
                precision_rounding=line.product_uom_id.rounding,
            ) <= 0:
                raise ValidationError(_("Repair service charge quantity must be greater than zero."))
            if line.price_unit < 0:
                raise ValidationError(_("Repair service charge amount cannot be negative."))
