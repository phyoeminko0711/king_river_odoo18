# Copyright 2019 Ecosoft Co., Ltd. (http://ecosoft.co.th)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval


class StockCardReportWizard(models.TransientModel):
    _name = "stock.card.report.wizard"
    _description = "Stock Card Report Wizard"

    date_range_id = fields.Many2one(comodel_name="date.range", string="Period")
    date_from = fields.Date(string="Start Date")
    date_to = fields.Date(string="End Date")

    #########################
    def _company_id_domain(self):
        return [('id', 'in', self.env.user.company_ids.ids)]

    company_id = fields.Many2one('res.company', 'Company', domain=_company_id_domain, default=lambda self: self.env.user.company_id.id)
    location_ids = fields.Many2many("stock.location", string="Locations", domain="[ '|', ('company_id', '=', False), ('company_id', '=', company_id),('usage', '=', 'internal')]")
    product_ids = fields.Many2many("product.product", string="Products", domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    category_id = fields.Many2one(
        comodel_name="product.category",
        string="Category"
    )
    check_no_move = fields.Boolean(string="Include no move in period")

    @api.onchange('category_id')
    def _onchange_category_id(self):
        if self.category_id:
            product_ids = self.env['product.product'].search([('categ_id', 'child_of', self.category_id.id)])
            return {'domain': {'product_ids': [('id', 'in', product_ids.ids)]}, 'value': {'product_ids': False}}
        if not self.category_id:
            self.update({'product_ids': False})


    ########################

    @api.onchange("date_range_id")
    def _onchange_date_range_id(self):
        self.date_from = self.date_range_id.date_start
        self.date_to = self.date_range_id.date_end

    def button_export_html(self):
        self.ensure_one()
        action = self.env.ref("stock_card_report.action_report_stock_card_report_html")
        vals = action.sudo().read()[0]
        context = vals.get("context", {})
        if context:
            context = safe_eval(context)
        model = self.env["report.stock.card.report"]
        report = model.create(self._prepare_stock_card_report())
        context["active_id"] = report.id
        context["active_ids"] = report.ids
        vals["context"] = context
        return vals

    def button_export_pdf(self):
        self.ensure_one()
        report_type = "qweb-pdf"
        return self._export(report_type)

    def button_export_xlsx(self):
        self.ensure_one()
        report_type = "xlsx"
        return self._export(report_type)

    def _prepare_stock_card_report(self):
        self.ensure_one()
        ###################
        if self.category_id:
            if not self.product_ids:
                product_ids = self.env['product.product'].search([('categ_id', 'child_of', self.category_id.id)])
            else:
                product_ids = self.product_ids
        elif self.product_ids:
            product_ids = self.product_ids
        else:
            product_ids = self.env["product.product"].search([])

        ###################
        return {
            "company_id": self.company_id.id,
            "date_from": self.date_from,
            "date_to": self.date_to or fields.Date.context_today(self),
            "product_ids": [(6, 0, product_ids.ids)],
            "location_ids": [(6, 0, self.location_ids.ids)],
            "category_id": self.category_id.id,
            "check_no_move": self.check_no_move,
            #########
        }

    def _export(self, report_type):
        model = self.env["report.stock.card.report"]
        report = model.create(self._prepare_stock_card_report())
        return report.print_report(report_type)
