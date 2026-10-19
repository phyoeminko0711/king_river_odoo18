from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
    company_price_unit = fields.Monetary(
        string="Company Unit Price",
        currency_field="company_currency_id",
        compute="_compute_company_price_unit",
        inverse="_inverse_company_price_unit",
        readonly=False,
        help="Enter the unit price in company currency. The purchase order unit price is converted using the order date's exchange rate.",
    )

    car_name = fields.Char(
        string="Car Name",
        related="product_id.product_tmpl_id.car_name",
        store=True,
        readonly=True,
    )
    lh_rh = fields.Char(
        string="LH/RH",
        related="product_id.product_tmpl_id.lh_rh",
        store=True,
        readonly=True,
    )
    model_engine = fields.Char(
        string="Model / Engine",
        related="product_id.product_tmpl_id.model_engine",
        store=True,
        readonly=True,
    )

    @api.depends("price_unit", "currency_id", "company_id", "date_order")
    def _compute_company_price_unit(self):
        for line in self:
            if not line.currency_id or not line.company_id:
                line.company_price_unit = 0.0
                continue
            line.company_price_unit = line.currency_id._convert(
                line.price_unit,
                line.company_id.currency_id,
                line.company_id,
                (line.date_order or fields.Datetime.now()).date(),
                round=False,
            )

    def _inverse_company_price_unit(self):
        for line in self:
            if line.currency_id and line.company_id:
                line.price_unit = line.company_id.currency_id._convert(
                    line.company_price_unit,
                    line.currency_id,
                    line.company_id,
                    (line.date_order or fields.Datetime.now()).date(),
                    round=False,
                )

    @api.onchange("company_price_unit")
    def _onchange_company_price_unit(self):
        self._inverse_company_price_unit()


    @api.onchange("product_id")
    def _onchange_product_apply_order_analytic_account(self):
        for line in self:
            if line.order_id.analytic_account_id and not line.display_type:
                line.analytic_distribution = line.order_id._get_header_analytic_distribution()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("analytic_distribution") or not vals.get("order_id"):
                continue
            order = self.env["purchase.order"].browse(vals["order_id"])
            if order.analytic_account_id:
                vals["analytic_distribution"] = order._get_header_analytic_distribution()
        return super().create(vals_list)
