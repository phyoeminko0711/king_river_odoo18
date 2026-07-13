import xlsxwriter
from odoo import api, models, fields, _
from odoo.exceptions import UserError
from io import BytesIO
import xlwt


class SaleDetailReport(models.TransientModel):
    _name = 'sale.detail.report'
    _description = 'Sale Detail Report'

    def _company_id_domain(self):
        return [('id', 'in', self.env.user.company_ids.ids)]

    company_id = fields.Many2one('res.company', 'Company', domain=_company_id_domain,
                                 default=lambda self: self.env.user.company_id.id)
    date_from = fields.Date(string="Date From")
    date_to = fields.Date(string="Date To")
    user_ids = fields.Many2many('res.users', string='Sales Person')
    customer_ids = fields.Many2many(
        'res.partner',
        string='Customer',
        domain=[('customer_rank', '>', 0), ('active', '=', True)]
    )

    sub_category_id = fields.Many2one(
        comodel_name="product.category",
        string="Sub Category"
    )
    product_ids = fields.Many2many(comodel_name="product.product",
                                   string="Products",
                                   domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    sale_team_ids = fields.Many2many('crm.team', string="Sale Team")



    # Add these fields
    group_category_domain = fields.Char(compute='_compute_group_category_domain', store=False)
    sub_category_domain = fields.Char(compute='_compute_sub_category_domain', store=False)

    @api.onchange('category_id')
    def _onchange_product(self):
        if self.category_id:
            product_tmpl_id = self.env['product.template'].search(
                [('categ_id', '=', self.category_id.id)])
            if product_tmpl_id:
                product_tmpl_id = tuple(product_tmpl_id.ids)
                return {'domain': {'product_ids': [('id', 'in', self.env["product.product"].
                                                    search([("product_tmpl_id", "in", product_tmpl_id)]).ids)]},
                        'value': {'product_ids': False}}

        if not self.category_id:
            self.update({
                'product_ids': False
            })
            return {'domain': {
                'product_ids': [('id', 'in', self.env["product.product"].search([("active", "=", True)]).ids)]}}

    def print_report(self):
        report_name = 'Sale Detail Report'
        records = self.get_data()
        return {
            'type': 'ir.actions.act_url',
            'url': '/download/excel?id=%s&model=%s&report_name=%s' % (self.id, self._name, report_name),
            'target': 'new',
        }

    def get_data(self):
        condition_str = " "

        if self.company_id:
            condition_str += " and sol.company_id = " + str(self.company_id.id)

        if self.date_from and self.date_to:
            condition_str += " and TO_CHAR(so.date_order, 'YYYY-MM-DD') between '" + str(self.date_from) + "' and '" + \
                             str(self.date_to) + "'"

        if self.customer_ids:
            cust_ids = tuple(self.customer_ids.ids)
            if len(cust_ids) == 1:
                condition_str += " and so.partner_id in ({})".format(cust_ids[0])
            else:
                condition_str += " and so.partner_id in {}".format(cust_ids)

        # Category filter - handle hierarchical categories


        if self.product_ids:
            pt_ids = tuple(self.product_ids.ids)
            if len(self.product_ids) == 1:
                condition_str += " and sol.product_id in ({})".format(pt_ids[0])
            else:
                condition_str += " and sol.product_id in {}".format(pt_ids)

        if self.user_ids:
            user_id = tuple(self.user_ids.ids)
            if len(user_id) == 1:
                condition_str += " and so.user_id in ({})".format(user_id[0])
            else:
                condition_str += " and so.user_id in {}".format(user_id)

        if self.sale_team_ids:
            team_ids = tuple(self.sale_team_ids.ids)
            if len(self.sale_team_ids) == 1:
                condition_str += " and so.team_id in ({})".format(team_ids[0])
            else:
                condition_str += " and so.team_id in {}".format(team_ids)

        # if self.sale_channel_ids:
        #     channel_ids = tuple(self.sale_channel_ids.ids)
        #     if len(self.sale_channel_ids) == 1:
        #         condition_str += " and so.sale_channel_id in ({})".format(channel_ids[0])
        #     else:
        #         condition_str += " and so.sale_channel_id in {}".format(channel_ids)

        self.env.cr.execute("""
                            SELECT
                        so.id AS order_id,
                        so.name AS order_no,
                        sol.id AS line_id,
                        sol.product_id,
                        TO_CHAR(so.date_order, 'YYYY-MM-DD') AS order_date,
                        partner.name AS customer,
                        ind.name->>'en_US' AS industry,
                        rc.name AS currency,
                        pc.name AS category_name, 
                        sol.product_uom_qty AS doc_qty,
                        sol.product_uom AS doc_uom,
                        uom_doc.name->>'en_US' AS doc_uom_name,
                        sol.qty_invoiced AS invoiced_doc_qty,
                        uom_invoice.name->>'en_US' AS invoiced_doc_uom,
                        sol.price_unit AS unit_price,
                        sol.discount AS discount_percent,
                        sol.qty_delivered AS delivered_doc_qty,
                        uom_delivered.name->>'en_US' AS delivered_doc_uom,
                        sol.price_subtotal AS subtotal,
                        ct.name->>'en_US' AS team_name,
                        he.name AS sale_man,
                        ptl.default_code AS product_code,
                        ptl.name->>'en_US' AS product_name,
                        sw.name AS warehouse_name
                    FROM sale_order so
                        LEFT JOIN res_users rs ON rs.id = so.user_id
                        LEFT JOIN hr_employee he ON he.user_id = rs.id
                        INNER JOIN sale_order_line sol ON so.id = sol.order_id
                        INNER JOIN res_partner partner ON partner.id = so.partner_id
                        LEFT JOIN res_partner_industry ind ON partner.industry_id = ind.id
                        INNER JOIN res_currency rc ON rc.id = so.currency_id 
                        INNER JOIN product_product pp ON pp.id = sol.product_id
                        INNER JOIN product_template ptl ON pp.product_tmpl_id = ptl.id
                        INNER JOIN product_category pc ON ptl.categ_id = pc.id
                        INNER JOIN crm_team ct ON ct.id = so.team_id
                        LEFT JOIN stock_warehouse sw ON so.warehouse_id = sw.id
                        LEFT JOIN uom_uom uom_doc ON uom_doc.id = sol.product_uom
                        LEFT JOIN uom_uom uom_invoice ON uom_invoice.id = sol.product_uom
                        LEFT JOIN uom_uom uom_delivered ON uom_delivered.id = sol.product_uom
                    WHERE so.state NOT IN ('draft', 'sent', 'cancel')
                    AND ptl.type IN ('consu', 'service')
              """ + condition_str + """
            GROUP BY
                    so.id, so.name, sol.id, sol.product_id, so.date_order,
                    partner.name, rc.name, pc.name, sol.price_unit,
                    sol.discount, ct.name, he.name, sol.product_uom_qty, 
                    sol.qty_delivered, sol.qty_invoiced, sol.product_uom,
                    ptl.default_code, ptl.name, uom_doc.name, uom_invoice.name,
                    uom_delivered.name,ind.name,sw.name
            ORDER BY so.date_order
        """)

        records = self.env.cr.dictfetchall()

        if not records:
            raise UserError(_('There is no data.'))
        return records

    def get_xlsx(self, response):
        records = self.get_data()
        excel = BytesIO()
        workbook = xlsxwriter.Workbook(excel, {'in_memory': True})
        sheet = workbook.add_worksheet('Sheet1')

        title_style = workbook.add_format({
            'font_name': 'Arial', 'font_size': 11,
            'valign': 'vcenter', 'align': 'center', 'bold': True,
            'bg_color': '#d3d3d3',
        })

        header_style_gray = workbook.add_format({
            'font_name': 'Arial', 'font_size': 10, 'bold': True,
            'valign': 'vcenter', 'align': 'center', 'border': 1,
            'bg_color': '#d3d3d3',
        })

        serial_no_style = workbook.add_format({
            'font_name': 'Arial', 'font_size': 9,
            'valign': 'vcenter', 'align': 'center', 'border': 1,
        })

        number_style = workbook.add_format({
            'font_name': 'Arial', 'font_size': 9,
            'valign': 'vcenter', 'align': 'right', 'border': 1,
            'num_format': '#,##0.00'
        })
        percent_format = workbook.add_format({'num_format': '0%'})

        y_offset = 0
        sheet.merge_range(y_offset, 0, y_offset, 33, 'Sale Detail Report', title_style)
        y_offset += 2
        sheet.write(y_offset, 0, _('From'), header_style_gray)
        sheet.write(y_offset, 1, self.date_from and str(self.date_from) or '', serial_no_style)
        y_offset += 1
        sheet.write(y_offset, 0, _('To'), header_style_gray)
        sheet.write(y_offset, 1, self.date_to and str(self.date_to) or '', serial_no_style)
        y_offset += 2

        # Create headers with correct column positions
        col = 0
        sheet.write(y_offset, col, _('Order No'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('Order Date'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('Customer'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('Industry'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('Sale Team'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('Sales Person'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('Currency'), header_style_gray);
        col += 1

        sheet.write(y_offset, col, _('Main Category'), header_style_gray);
        col += 1

        sheet.write(y_offset, col, _('Group Category'), header_style_gray);
        col += 1

        sheet.write(y_offset, col, _('Sub Category'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('Product Code'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('Product Name'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('Warehouse'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('Doc Uom'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('Doc Qty'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('TC Doc Uom'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('TC Doc Qty'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('Delivered Doc Uom'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('Delivered Doc Qty'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('Invoice Doc Uom'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('Invoice Doc Qty'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('Unit Price'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('Discount%'), header_style_gray);
        col += 1
        sheet.write(y_offset, col, _('SubTotal'), header_style_gray)

        # Write data rows
        for record in records:
            y_offset += 1
            product = self.env['product.product'].browse(record.get('product_id'))

            # TC qty and uom same as delivered if use_transportation_charges is True
            use_tc = record.get('use_transportation_charges', False)
            tc_doc_uom = record.get('delivered_doc_uom', '') if use_tc else ''
            tc_doc_qty = record.get('delivered_doc_qty', 0.0) if use_tc else 0.0

            col = 0
            sheet.write(y_offset, col, record.get('order_no', ''), serial_no_style);
            col += 1
            sheet.write(y_offset, col, record.get('order_date', ''), serial_no_style);
            col += 1
            sheet.write(y_offset, col, record.get('customer', ''), serial_no_style);
            col += 1
            sheet.write(y_offset, col, record.get('industry', ''), serial_no_style);
            col += 1
            sheet.write(y_offset, col, record.get('team_name', ''), serial_no_style);
            col += 1
            sheet.write(y_offset, col, record.get('sale_man', ''), serial_no_style);
            col += 1
            sheet.write(y_offset, col, record.get('currency', ''), serial_no_style);
            col += 1

            sheet.write(y_offset, col, product.categ_id.parent_id.parent_id.name or '', serial_no_style);
            col += 1

            sheet.write(y_offset, col, product.categ_id.parent_id.name or '', serial_no_style);
            col += 1

            sheet.write(y_offset, col, product.categ_id.name or '', serial_no_style);
            col += 1
            sheet.write(y_offset, col, record.get('product_code', ''), serial_no_style);
            col += 1
            sheet.write(y_offset, col, record.get('product_name', ''), serial_no_style);
            col += 1
            sheet.write(y_offset, col, record.get('warehouse_name', ''), serial_no_style);
            col += 1
            sheet.write(y_offset, col, record.get('doc_uom_name', ''), serial_no_style);
            col += 1
            sheet.write(y_offset, col, record.get('doc_qty', 0.0), number_style);
            col += 1
            sheet.write(y_offset, col, tc_doc_uom, serial_no_style);
            col += 1
            sheet.write(y_offset, col, tc_doc_qty, number_style);
            col += 1
            sheet.write(y_offset, col, record.get('delivered_doc_uom', ''), serial_no_style);
            col += 1
            sheet.write(y_offset, col, record.get('delivered_doc_qty', 0.0), number_style);
            col += 1
            sheet.write(y_offset, col, record.get('invoiced_doc_uom', ''), serial_no_style);
            col += 1
            sheet.write(y_offset, col, record.get('invoiced_doc_qty', 0.0), number_style);
            col += 1
            sheet.write(y_offset, col, record.get('unit_price', 0.0), number_style);
            col += 1
            sheet.write(y_offset, col, record.get('discount_percent', 0.0), number_style);
            col += 1
            sheet.write(y_offset, col, record.get('subtotal', 0.0), number_style)

        # Set column widths
        sheet.set_column(0, 33, 18)

        workbook.close()
        excel.seek(0)
        response.stream.write(excel.read())
        excel.close()
