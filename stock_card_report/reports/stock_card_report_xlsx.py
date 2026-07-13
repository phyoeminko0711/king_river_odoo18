# Copyright 2019 Ecosoft Co., Ltd. (http://ecosoft.co.th)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import models, _


_logger = logging.getLogger(__name__)


class ReportStockCardReportXlsx(models.AbstractModel):
    _name = "report.stock_card_report.report_stock_card_report_xlsx"
    _description = "Stock Card Report XLSX"
    _inherit = "report.report_xlsx.abstract"

    def generate_xlsx_report(self, workbook, data, objects):
        #################Define Format############
        format_title = workbook.add_format({
            'bold': True,
            'align': 'center',
            'font_size': 14,
        })
        format_header = workbook.add_format({
            'bold': True,
            'bg_color': '#FFFFCC',
            'border': True
        })
        format_header_right = workbook.add_format({
            'bold': True,
            'bg_color': '#FFFFCC',
            'border': True,
            'align': 'right'
        })
        format_title_center = workbook.add_format({
            'bold': True,
            'bg_color': '#99c1f2',
            'border': True,
            'align': 'center',
            'font_size': 12,
        })
        format_header_center = workbook.add_format({
            'bold': True,
            'bg_color': '#FFFFFF',
            'border': True,
            'align': 'center',
            'font_size': 9,
        })
        format_header_center_blue = workbook.add_format({
            'bold': True,
            'bg_color': '#99c1f2',
            'border': True,
            'align': 'center',
            'font_size': 9,
        })
        format_header_center_gray = workbook.add_format({
            'bold': True,
            'bg_color': '#d3d3d3',
            'border': True,
            'align': 'center',
            'font_size': 9,
        })

        format_data = workbook.add_format({
            'border': True,
            'align': 'left',
            'font_size': 9,
        })
        format_data_right_justify = workbook.add_format({
            'border': True,
            'align': 'right',
            'font_size': 9,
        })

        currency_format = workbook.add_format({
            'num_format': '#,##0.00',
            'border': True,
            'align': 'right',
            'font_size': 9,
        })
        currency_format_gray = workbook.add_format({
            'num_format': '#,##0.00',
            'border': True,
            'align': 'right',
            'font_size': 9,
            'bg_color': '#d3d3d3',
        })
        format_filter_left_bold = workbook.add_format({
            'border': True,
            'align': 'left',
            'bold': True,
        })
        format_filter_right_bold = workbook.add_format({
            'border': True,
            'align': 'right',
            'bold': True,
        })
        #############################
        y_offset = 0
        sheet = workbook.add_worksheet('sheet')
        row_no = 0
        sheet.merge_range(y_offset, 0, y_offset, 10, 'Stock Card Report', format_title_center)
        y_offset += 2
        sheet.write(y_offset, 0, _('From'), format_filter_left_bold)
        sheet.write(y_offset, 1, objects.date_from and str(objects.date_from) or '', format_filter_right_bold)
        y_offset += 1
        sheet.write(y_offset, 0, _('To'), format_filter_left_bold)
        sheet.write(y_offset, 1, str(objects.date_to) or '', format_filter_right_bold)
        y_offset += 1

        if objects.location_ids:
            location_names = ', '.join([l.complete_name for l in objects.location_ids])
            sheet.write(y_offset, 0, _('Location'), format_filter_left_bold)
            sheet.write(y_offset, 1, location_names or '', format_filter_right_bold)
        else:
            sheet.write(y_offset, 0, _('Location'), format_filter_left_bold)
            sheet.write(y_offset, 1, 'All', format_filter_right_bold)



        stock_card_dict = objects._compute_results()
        for pid, stock_line in stock_card_dict.items():
            if not objects.check_no_move:
                if stock_line['balance'] == 0 and stock_line['ending_balance_value'] == 0 and len(
                        stock_line['product_lines']) == 0:
                    continue
            y_offset += 3
            sheet.merge_range(y_offset, 0, y_offset, 10, stock_line['name'], format_header_center_blue)
            y_offset += 1
            sheet.set_column(y_offset, 0, 15)
            sheet.write(y_offset, 0, _('Date'), format_header_center_gray)
            sheet.set_column(y_offset, 1, 10)
            sheet.write(y_offset, 1, _('Reference'), format_header_center_gray)
            sheet.set_column(y_offset, 2, 16)
            sheet.write(y_offset, 2, _('LOT/Serial No'), format_header_center_gray)
            sheet.set_column(y_offset, 3, 10)
            sheet.write(y_offset, 3, _('In Qty'), format_header_center_gray)
            sheet.set_column(y_offset, 4, 10)
            sheet.write(y_offset, 4, _('Out Qty'), format_header_center_gray)
            sheet.set_column(y_offset, 5, 15)
            sheet.write(y_offset, 5, _('Balance Qty'), format_header_center_gray)
            sheet.set_column(y_offset, 6, 20)
            sheet.write(y_offset, 6, _('CPU'), format_header_center_gray)
            sheet.set_column(y_offset, 7, 20)
            sheet.write(y_offset, 7, _('Total'), format_header_center_gray)
            sheet.set_column(y_offset, 8, 20)
            sheet.write(y_offset, 8, _('Balance Value'), format_header_center_gray)
            sheet.set_column(y_offset, 9, 25)
            sheet.write(y_offset, 9, _('From Warehouse'), format_header_center_gray)
            sheet.set_column(y_offset, 10, 25)
            sheet.write(y_offset, 10, _('To Warehouse'), format_header_center_gray)
            sheet.set_column(y_offset, 6, 25)

            y_offset += 1
            sheet.merge_range(y_offset, 0, y_offset, 4, 'Initial', format_header_center)
            sheet.write(y_offset, 5, "{:.2f}".format(stock_line['balance']), format_data_right_justify)
            sheet.write(y_offset, 6, '', format_data_right_justify)
            sheet.write(y_offset, 7, '', format_data_right_justify)
            sheet.write(y_offset, 8, "{:.2f}".format(stock_line['ending_balance_value']), format_data_right_justify)
            sheet.write(y_offset, 9, '', format_data_right_justify)
            sheet.write(y_offset, 10, '', format_data_right_justify)
            sheet.write(y_offset, 6, '', format_data_right_justify)
            sheet.write(y_offset, 7, '', format_data_right_justify)

            balance = stock_line['balance']
            ending_balance_value = stock_line['ending_balance_value']
            total_in_qty = 0.0
            total_out_qty = 0.0
            total_balance = 0
            total_ending_value = 0.0

            for line in stock_line['product_lines']:
                y_offset += 1
                balance += (line['product_in'] - line['product_out'])
                ending_balance_value += line['value'] * (line['product_in'] - line['product_out'])
                row_no += 1
                sheet.write(y_offset, 0, str(line['date']), format_data)
                sheet.write(y_offset, 1, line['reference'], format_data)
                sheet.write(y_offset, 2, line['serial_no'], format_data)
                sheet.write(y_offset, 3, line['product_in'], format_data_right_justify)
                sheet.write(y_offset, 4, line['product_out'], format_data_right_justify)
                sheet.write(y_offset, 5, balance, format_data_right_justify)
                sheet.write(y_offset, 6, line['value'], currency_format)
                sheet.write(y_offset, 7, line['value'] * abs(line['product_in'] - line['product_out']),
                            currency_format)
                sheet.write(y_offset, 8, ending_balance_value, currency_format)
                sheet.write(y_offset, 9, line['source'], format_data)
                sheet.write(y_offset, 10, line['destination'], format_data)
                total_in_qty += line['product_in']
                total_out_qty += line['product_out']
                total_balance = balance
                total_ending_value = ending_balance_value

            y_offset += 1
            sheet.merge_range(y_offset, 0, y_offset, 2, 'Total', format_header_center_gray)
            sheet.write(y_offset, 3, total_in_qty, currency_format_gray)
            sheet.write(y_offset, 4, total_out_qty, currency_format_gray)
            sheet.write(y_offset, 5, total_balance, currency_format_gray)
            sheet.write(y_offset, 6, '', currency_format_gray)
            sheet.write(y_offset, 7, '', currency_format_gray)
            sheet.write(y_offset, 8, total_ending_value, currency_format_gray)
            sheet.write(y_offset, 9, '', currency_format_gray)
            sheet.write(y_offset, 10, '', currency_format_gray)
