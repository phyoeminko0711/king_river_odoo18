import xlsxwriter
from odoo import api, models, fields, _
from odoo.exceptions import UserError
from io import BytesIO


class PurchaseDetailReport(models.TransientModel):
    _name = 'purchase.detail.report'
    _description = 'Purchase Detail Report'

    def _company_id_domain(self):
        return [('id', 'in', self.env.user.company_ids.ids)]

    company_id = fields.Many2one('res.company', 'Company', domain=_company_id_domain,
                                 default=lambda self: self.env.user.company_id.id)
    date_from = fields.Date(string="Date From")
    date_to = fields.Date(string="Date To")
    vendor_ids = fields.Many2many('res.partner', string='Vendors')

    product_ids = fields.Many2many(comodel_name="product.product",
                                   string="Products",
                                   domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")





    def print_report(self):
        report_name = 'Purchase Detail Report'
        records = self.get_data()
        return {
            'type': 'ir.actions.act_url',
            'url': '/download/excel?id=%s&model=%s&report_name=%s' % (self.id, self._name, report_name),
            'target': 'new',
        }

    def get_data(self):
        condition_str = " "
        # import pdb
        # pdb.set_trace()
        if self.company_id:
            condition_str += " and pol.company_id = " + str(self.company_id.id)

        if self.date_from and self.date_to:
            condition_str += " and TO_CHAR(po.date_order, 'YYYY-MM-DD') between '" + str(
                self.date_from) + "' and '" + \
                             str(self.date_to) + "'"

        if self.vendor_ids:
            vend_ids = tuple(self.vendor_ids.ids)
            if len(vend_ids) == 1:
                condition_str += " and po.partner_id in ({})".format(vend_ids[0])
            else:
                condition_str += " and po.partner_id in {}".format(vend_ids)

        if self.product_ids:
            pt_ids = tuple(self.product_ids.ids)
            if len(self.product_ids) == 1:
                condition_str += " and pol.product_id in ({})".format(pt_ids[0])
            else:
                condition_str += " and pol.product_id in {}".format(pt_ids)

        self.env.cr.execute("""
                select po.name as oder_no,pol.product_id,TO_CHAR(po.date_order, 'YYYY-MM-DD') as order_date,
                partner.name as vendor,rc.name as currency,pc.name as category, ptl.default_code as part_no,
                pol.product_uom_qty as quantity,pol.qty_received as received_qty, sl.complete_name as location,
                pol.qty_invoiced as invoiced_qty,pol.price_unit as unit_price, pol.price_subtotal as subtotal
                from purchase_order po
                inner join purchase_order_line pol on po.id = pol.order_id
                left join stock_picking sp on sp.origin = po.name
                left join stock_location sl on sl.id = sp.location_dest_id
                inner join res_partner partner on partner.id = po.partner_id
                inner join res_currency rc on rc.id = pol.currency_id
                inner join product_product pp on pp.id = pol.product_id
                inner join product_template ptl on pp.product_tmpl_id = ptl.id
                inner join product_category pc on ptl.categ_id = pc.id	
                where po.state not in ('draft', 'cancel')
                """ + condition_str + """ order by po.date_order """)
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

        header_style = workbook.add_format({
            'font_name': 'Arial', 'font_size': 10, 'bold': True,
            'valign': 'vcenter', 'align': 'center', 'border': 1,
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

        label_cell_style = workbook.add_format({
            'font_name': 'Arial', 'font_size': 9,
            'valign': 'vcenter', 'align': 'left',
        })

        number_cell_style = workbook.add_format({
            'font_name': 'Arial', 'font_size': 9, 'right': 1,
            'valign': 'vcenter', 'align': 'right', 'num_format': '#,##0K'
        })

        footer_label_style = workbook.add_format({
            'font_name': 'Arial', 'font_size': 9, 'top': 1, 'bottom': 1,
            'valign': 'vcenter', 'align': 'left', 'bold': True,
        })

        footer_number_style = workbook.add_format({
            'font_name': 'Arial', 'font_size': 9, 'top': 1, 'bottom': 1, 'right': 1,
            'valign': 'vcenter', 'align': 'right', 'num_format': '#,##0K', 'bold': True,
        })

        y_offset = 0
        row_no = 0
        sheet.merge_range(y_offset, 0, y_offset, 12, 'Purchase Detail Report', title_style)
        y_offset += 2
        sheet.write(y_offset, 0, _('From'), header_style_gray)
        sheet.write(y_offset, 1, self.date_from and str(self.date_from) or '', serial_no_style)
        y_offset += 1
        sheet.write(y_offset, 0, _('To'), header_style_gray)
        sheet.write(y_offset, 1, self.date_to and str(self.date_to) or '', serial_no_style)
        y_offset += 2
        # create header
        sheet.write(y_offset, 0, _('Oder No'), header_style_gray)
        sheet.write(y_offset, 1, _('Order Date'), header_style_gray)
        sheet.write(y_offset, 2, _('Vendor'), header_style_gray)
        sheet.write(y_offset, 3, _('Curreny'), header_style_gray)
        sheet.write(y_offset, 4, _('Product Category'), header_style_gray)
        sheet.write(y_offset, 5, _('Product Code'), header_style_gray)
        sheet.write(y_offset, 6, _('Product Name'), header_style_gray)
        sheet.write(y_offset, 7, _('Qty'), header_style_gray)
        sheet.write(y_offset, 8, _('Received Qty'), header_style_gray)
        sheet.write(y_offset, 9, _('Invoice Qty'), header_style_gray)
        sheet.write(y_offset, 10, _('Unit Price'), header_style_gray)
        sheet.write(y_offset, 11, _('SubTotal'), header_style_gray)
        sheet.write(y_offset, 12, _('Location'), header_style_gray)

        for record in records:
            y_offset += 1
            product = self.env['product.product'].browse(record['product_id'])
            sheet.write(y_offset, 0, record['oder_no'], serial_no_style)
            sheet.write(y_offset, 1, record['order_date'], serial_no_style)
            sheet.write(y_offset, 2, record['vendor'], serial_no_style)
            sheet.write(y_offset, 3, record['currency'], serial_no_style)
            sheet.write(y_offset, 4, record['category'], serial_no_style)
            sheet.write(y_offset, 5, record['part_no'], serial_no_style)
            sheet.write(y_offset, 6, product.name, serial_no_style)
            sheet.write(y_offset, 7, record['quantity'], serial_no_style)
            sheet.write(y_offset, 8, record['received_qty'], serial_no_style)
            sheet.write(y_offset, 9, record['invoiced_qty'], serial_no_style)
            sheet.write(y_offset, 10, record['unit_price'], serial_no_style)
            sheet.write(y_offset, 11, record['subtotal'], serial_no_style)
            sheet.write(y_offset, 12, record['location'], serial_no_style)

        sheet.set_column(4, 6, 17)

        workbook.close()
        excel.seek(0)
        response.stream.write(excel.read())
        excel.close()