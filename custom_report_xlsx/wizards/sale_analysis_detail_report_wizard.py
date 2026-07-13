# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import date, datetime, time
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError
from io import BytesIO
import xlsxwriter


class SaleAnalysisReportWizard(models.TransientModel):
    _name = 'wizard.sale.analysis.report'

    def _company_id_domain(self):
        return [('id', 'in', self.env.user.company_ids.ids)]

    company_id = fields.Many2one('res.company', 'Company', domain=_company_id_domain)
    from_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")
    vehicle_id = fields.Many2one('res.partner', string='Vehicle',domain="['&','|', ('company_id', '=', False), ('company_id', '=', company_id),('customer_rank', '>', 0)]", )
    product_id = fields.Many2one('product.product', string='Product',domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    invoice_id = fields.Many2one('account.move', string='Invoice No.',domain="['&','|', ('company_id', '=', False), ('company_id', '=', company_id),('state','=','posted')]")
    division_id = fields.Many2one('res.country.state', string='Division')
    sale_team_ids = fields.Many2many('crm.team',string="Sale Team")


    def print_report(self):
        report_name = 'Sale Analysis Detail Report'
        records = self.get_invs()
        return {
            'type': 'ir.actions.act_url',
            'url': '/download/excel?id=%s&model=%s&report_name=%s' % (self.id, self._name, report_name),
            'target': 'new',
        }

    def get_invs(self):
        # import pdb;pdb.set_trace()
        condition_str = " "
        if self.from_date and self.to_date:
            condition_str += " and am.invoice_date between '" + str(self.from_date) + "' and '" + str(self.to_date) + "'"
        if self.company_id:
            condition_str += " and am.company_id = " + str(self.company_id.id)
        # else:
        #     condition_str += " and am.company_id in " + " (select cid from res_company_users_rel where user_id= " + str(
        #         self.env.user.id) + ")"
        if self.vehicle_id:
            condition_str += " and am.partner_id = " + str(self.vehicle_id.id)
        if self.division_id:
            condition_str += " and ap.state_id = " + str(self.division_id.id)

        if self.invoice_id:
            condition_str += " and am.id = " + str(self.invoice_id.id)
        self.env.cr.execute("""                         
                			select am.invoice_origin as inv from account_move am
                            inner join res_partner ap on am.partner_id=ap.id
                            where am.move_type in ('out_invoice') and am.state  in ('posted')
                            and am.invoice_origin is not null
                            """ + condition_str + """ GROUP BY  am.invoice_origin order by am.invoice_origin  
                            """)
        invs = self.env.cr.dictfetchall()
        if not invs:
            raise UserError(_('There is no data.'))

        return invs

    def get_data(self, inv):
        condition_str = " "

        condition_str += " and am.invoice_origin = '" + inv['inv'] + "'"

        if self.product_id:
            condition_str += " and aml.product_id = " + str(self.product_id.id)


        if self.from_date and self.to_date:
            condition_str += " and am.invoice_date between '" + str(self.from_date) + "' and '" + str(self.to_date) + "'"
        if self.from_date and not self.to_date:
            condition_str += " and am.invoice_date >= '" + str(self.from_date) + "'"
        if not self.from_date and self.to_date:
            condition_str += " and am.invoice_date <= '" + str(self.to_date) + "'"

        if self.sale_team_ids:
            team_ids = tuple(self.sale_team_ids.ids)
            if len(self.sale_team_ids) == 1:
                condition_str += " and am.team_id in ({})".format(team_ids[0])
            else:
                condition_str += " and am.team_id in {}".format(team_ids)
        self.env.cr.execute("""                         
                        			SELECT 
                                    TO_CHAR(am.create_date + INTERVAL '6 hours 30 min', 'DD-MON-YYYY HH24:MI:SS') AS creation_date,
                                    TO_CHAR(am.invoice_date, 'dd-Mon-YYYY') AS invoice_date,
                                    am.name AS invoice_number,
                                    am.invoice_origin AS source_doc,
                                    ap.id AS customer_id,
                                    ap.name AS partner_name,
                                    aml.product_id,
                                    (SELECT name FROM product_category WHERE id = (SELECT parent_id FROM product_category WHERE id = pt.categ_id)) AS product_group,
                                    (SELECT name FROM product_category WHERE id = pt.categ_id) AS product_categ,
                                    CASE WHEN (aml.discount = 100 OR aml.quantity = 0) THEN 0
                                         ELSE ROUND(((aml.credit / (1 - (aml.discount / 100))) / aml.quantity), 2)
                                    END AS selling_price,
                                    aml.discount,
	                                aml.quantity quantity,
                                    aml.price_unit AS price,
                                    aml.credit AS net_price,
                                    am.amount_untaxed_signed,
                                    am.amount_tax_signed,
                                    am.ref AS customer_reference,
                                    am.amount_total_signed AS total,
                                    am.amount_residual_signed AS balance,
                                    am.amount_total AS amount_total,
                                    aml.price_subtotal AS price_subtotal,
                                    am.state,
                                    ct.name AS team_name,
                                    (SELECT name FROM res_company WHERE id = am.company_id) AS company,
                                    am.id AS invoice_id,
                                    pt.default_code AS product_code,
                                    at.name AS tax_name,
                                    at.amount AS tax_rate,
                                    -- Calculating tax amount
                                    ROUND(aml.price_subtotal * (at.amount / 100), 2) AS tax_amount
                                FROM 
                                    account_move am
                                INNER JOIN 
                                    account_move_line aml ON am.id = aml.move_id
                                INNER JOIN 
                                    res_partner ap ON am.partner_id = ap.id
                                INNER JOIN 
                                    product_product pp ON pp.id = aml.product_id
                                INNER JOIN 
                                    product_template pt ON pt.id = pp.product_tmpl_id
                                INNER JOIN 
                                    sale_order so ON so.name = am.invoice_origin
                                INNER JOIN 
                                    crm_team ct ON ct.id = am.team_id
                                LEFT JOIN 
                                    account_move_line_account_tax_rel aml_tax_rel ON aml.id = aml_tax_rel.account_move_line_id
                                LEFT JOIN 
                                    account_tax at ON aml_tax_rel.account_tax_id = at.id
                                WHERE 
                                    am.move_type = 'out_invoice' 
                                    AND am.state = 'posted'
                                    AND aml.display_type = 'product'
                                    """ + condition_str + """ order by am.id,am.invoice_origin
                                    """)
        datas = self.env.cr.dictfetchall()
        return datas
     # @api.multi

    def get_xlsx(self, response):
        inv_records = self.get_invs()
        excel = BytesIO()

        workbook = xlsxwriter.Workbook(excel, {'in_memory': True})
        title_style = workbook.add_format({
            'font_name': 'Arial', 'font_size': 11,
            'valign': 'vcenter', 'align': 'center', 'bold': True,
            'bg_color': '#d3d3d3',
        })

        format_header_center = workbook.add_format({
            'font_name': 'Arial', 'font_size': 10, 'bold': True,
            'valign': 'vcenter', 'align': 'center', 'border': 1,
            'bg_color': '#d3d3d3',
        })
        format_header_right = workbook.add_format({
            'bold': True,
            'border': True,
            'align': 'right',
            'font_size': 9,
        })
        format_data = workbook.add_format({
            'font_name': 'Arial', 'font_size': 9,
            'valign': 'vcenter', 'align': 'center', 'border': 1,
        })
        background = workbook.add_format({
            'bold': True,
            'border': True,
            'font_size': 9,
            'align': 'right',
        })

        y_offset = 0
        sheet = workbook.add_worksheet("Sale Analysis Detail")
        sheet.merge_range(y_offset, 0, y_offset, 14, _('Sale Analysis Detail Report'), title_style)
        y_offset += 2
        sheet.write(y_offset, 0, _('From'), format_header_center)
        sheet.write(y_offset, 1, self.from_date and str(self.from_date) or '', format_data)
        y_offset += 1
        sheet.write(y_offset, 0, _('To'), format_header_center)
        sheet.write(y_offset, 1, self.to_date and str(self.to_date) or '', format_data)
        y_offset += 2
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd', 'border': True, 'align': 'center'})
        number_format = workbook.add_format(
            {'num_format': '#,##0.00', 'border': True, 'bold': True, 'font_size': 9, 'align': 'right', })
        number_format_1 = workbook.add_format(
            {'num_format': '#,##0.00', 'border': True, 'font_size': 9, 'align': 'right', })
        sheet.write(y_offset, 0, _('No'), format_header_center)
        sheet.write(y_offset, 1, _('Invoice Date'), format_header_center)
        sheet.write(y_offset, 2, _('Invoice Number'), format_header_center)
        sheet.write(y_offset, 3, _('Source Document'), format_header_center)
        sheet.write(y_offset, 4, _('Customer Name'), format_header_center)
        sheet.write(y_offset, 5, _('Invoice Item Name'), format_header_center)
        sheet.write(y_offset, 6, _('Product Code'), format_header_center)
        sheet.write(y_offset, 7, _('Quantity'), format_header_center)
        sheet.write(y_offset, 8, _('Invoice Selling Price'), format_header_center)
        sheet.write(y_offset, 9, _('Invoice Net Price'), format_header_center)
        sheet.write(y_offset, 10, _('Taxed Amount'), format_header_center)
        sheet.write(y_offset, 11, _('Invoice Total'), format_header_center)
        sheet.write(y_offset, 12, _('Invoice Balance'), format_header_center)
        sheet.write(y_offset, 13, _('Company'), format_header_center)
        sheet.write(y_offset, 14, _('Sale Team'), format_header_center)

        y_offset += 1
        row_no = 0
        grand_total = 0
        for inv in inv_records:
            records = self.get_data(inv)
            rec_count = len(records)
            count = 0
            for record in records:
                count += 1
                row_no += 1
                tax = record['tax_amount']
                net_price = record['quantity']* record['price']
                discount = record['discount']
                amount = record['quantity']*(record['price'] * (discount / 100))
                discount_amount = (net_price * (discount / 100))
                if tax :
                    invoice_total = record['price_subtotal']+tax
                else:
                    invoice_total = record['price_subtotal']+0.0
                total = record['amount_untaxed_signed']+record['amount_tax_signed']

                product = self.env['product.product'].browse(record['product_id'])
                sheet.write(y_offset, 0, row_no, format_data)
                sheet.write(y_offset, 1, record['invoice_date'], format_data)
                sheet.write(y_offset, 2, record['invoice_number'], format_data)
                sheet.write(y_offset, 3, record['source_doc'], format_data)
                sheet.write(y_offset, 4, record['partner_name'], format_data)
                sheet.write(y_offset, 5, product.name, format_data)
                sheet.write(y_offset, 6, record['product_code'], format_data)
                sheet.write(y_offset, 7, record['quantity'], number_format_1)
                sheet.write(y_offset, 8, record['price'], number_format_1)
                sheet.write(y_offset, 9,net_price, number_format_1)
                if tax :
                    sheet.write(y_offset, 10, tax, number_format_1)
                else:
                    sheet.write(y_offset, 10, 0.0, number_format_1)
                sheet.write(y_offset, 11,invoice_total, number_format_1)
                if rec_count != count:
                    sheet.write(y_offset, 12, 0, number_format_1)
                else:
                    sheet.write(y_offset, 12, record['balance'], number_format_1)
                    grand_total += total
                sheet.write(y_offset, 13, record['company'], format_data)
                sheet.write(y_offset, 14, [*record['team_name'].values()][0], format_data)

                y_offset += 1

        sheet.merge_range(y_offset, 0, y_offset, 10, 'Grand Total', format_header_right)
        sheet.write(y_offset, 11, grand_total, number_format)

        sheet.set_column(0, 0, 11)
        sheet.set_column(1, 17, 28)
        workbook.close()
        excel.seek(0)
        response.stream.write(excel.read())
        excel.close()
