# -*- coding: utf-8 -*-
from collections import defaultdict
from io import BytesIO
import re

import xlsxwriter

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DailySalesSummaryWizard(models.TransientModel):
    _name = "daily.sales.summary.wizard"
    _description = "Daily Sales Summary Excel Wizard"

    def _company_id_domain(self):
        return [("id", "in", self.env.user.company_ids.ids)]

    date_from = fields.Date(
        string="From Date",
        required=True,
        default=lambda self: fields.Date.context_today(self),
    )
    date_to = fields.Date(
        string="To Date",
        required=True,
        default=lambda self: fields.Date.context_today(self),
    )
    sales_team_id = fields.Many2one("crm.team", string="Sales Team")
    salesperson_id = fields.Many2one("res.users", string="Salesperson")
    customer_id = fields.Many2one("res.partner", string="Customer")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        domain=_company_id_domain,
        default=lambda self: self.env.user.company_id.id,
    )

    @api.constrains("date_from", "date_to")
    def _check_date_range(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_("From Date cannot be later than To Date."))

    def print_report(self):
        self.ensure_one()
        self._check_date_range()
        report_name = self._xlsx_filename(
            "Daily Sales Summary",
            self.date_from,
            self.date_to,
            with_extension=False,
        )
        return {
            "type": "ir.actions.act_url",
            "url": "/download/excel?id=%s&model=%s&report_name=%s"
            % (self.id, self._name, report_name),
            "target": "new",
        }

    def get_xlsx(self, response):
        self.ensure_one()
        report_data = self._get_report_data()
        excel = BytesIO()
        workbook = xlsxwriter.Workbook(excel, {"in_memory": True})
        worksheet = workbook.add_worksheet(_("Daily Sales Summary")[:31])
        formats = self._get_xlsx_formats(workbook)

        columns = self._get_columns(report_data)
        last_col = len(columns) - 1
        self._write_report_header(worksheet, formats, last_col)

        header_row = 9
        for col, column_name in enumerate(columns):
            worksheet.write(header_row, col, column_name, formats["header"])

        totals = defaultdict(float)
        row = header_row + 1
        for index, line in enumerate(report_data["lines"], start=1):
            self._write_detail_row(worksheet, formats, row, index, line, report_data)
            self._accumulate_totals(totals, line, report_data)
            row += 1

        self._write_total_row(worksheet, formats, row, columns, totals, report_data)
        worksheet.freeze_panes(header_row + 1, 0)
        worksheet.autofilter(header_row, 0, max(row, header_row + 1), last_col)
        self._set_column_widths(worksheet, columns)

        workbook.close()
        excel.seek(0)
        response.stream.write(excel.read())
        excel.close()

    def _get_report_data(self):
        invoices = self._get_invoices()
        payment_data = self._get_reconciled_payment_data(invoices)
        payment_columns = self._get_payment_columns(payment_data)

        lines = []
        for invoice in invoices.sorted(key=lambda move: (move.invoice_date, move.name or "")):
            sale_orders = invoice.line_ids.sale_line_ids.order_id
            payment_amounts = {
                column_name: payment_data["payment_amounts"][invoice.id].get(column_name, 0.0)
                for column_name in payment_columns
            }

            lines.append(
                {
                    "invoice": invoice,
                    "sale_orders": sale_orders,
                    "order_number": self._format_sale_order_names(invoice, sale_orders),
                    "order_date": self._get_order_date(sale_orders),
                    "salesperson": self._get_salesperson(invoice, sale_orders),
                    "sales_team": self._get_sales_team(invoice, sale_orders),
                    "amount_invoiced": invoice.amount_total_signed,
                    "amount_due": invoice.amount_residual_signed,
                    "amount_paid": invoice.amount_total_signed - invoice.amount_residual_signed,
                    "payment_amounts": payment_amounts,
                }
            )

        return {
            "payment_columns": payment_columns,
            "lines": lines,
        }

    def _get_invoices(self):
        domain = [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
            ("company_id", "=", self.company_id.id),
        ]
        if self.customer_id:
            domain.append(("partner_id", "=", self.customer_id.id))

        invoices = self.env["account.move"].search(domain, order="invoice_date, name, id")
        if self.sales_team_id:
            invoices = invoices.filtered(
                lambda move: move.team_id == self.sales_team_id
                or self.sales_team_id in move.line_ids.sale_line_ids.order_id.mapped("team_id")
            )
        if self.salesperson_id:
            invoices = invoices.filtered(
                lambda move: move.invoice_user_id == self.salesperson_id
                or self.salesperson_id in move.line_ids.sale_line_ids.order_id.mapped("user_id")
            )
        return invoices

    def _get_reconciled_payment_data(self, invoices):
        payment_amounts = defaultdict(lambda: defaultdict(float))
        used_channel_names = set()
        used_journal_names = set()

        payment_term_lines = invoices.line_ids.filtered(
            lambda line: line.account_id.account_type
            in ("asset_receivable", "liability_payable")
        )
        invoice_line_by_id = {line.id: line.move_id for line in payment_term_lines}
        partials = payment_term_lines.matched_debit_ids | payment_term_lines.matched_credit_ids

        for partial in partials:
            if partial.debit_move_id.id in invoice_line_by_id:
                self._classify_partial_amount(
                    partial,
                    partial.debit_move_id,
                    partial.credit_move_id,
                    invoice_line_by_id,
                    payment_amounts,
                    used_channel_names,
                    used_journal_names,
                )
            if partial.credit_move_id.id in invoice_line_by_id:
                self._classify_partial_amount(
                    partial,
                    partial.credit_move_id,
                    partial.debit_move_id,
                    invoice_line_by_id,
                    payment_amounts,
                    used_channel_names,
                    used_journal_names,
                )

        return {
            "payment_amounts": payment_amounts,
            "used_channel_names": used_channel_names,
            "used_journal_names": used_journal_names,
        }

    def _classify_partial_amount(
        self,
        partial,
        invoice_line,
        counterpart_line,
        invoice_line_by_id,
        payment_amounts,
        used_channel_names,
        used_journal_names,
    ):
        invoice = invoice_line_by_id[invoice_line.id]
        sign = -1.0 if invoice.move_type == "out_refund" else 1.0
        amount = sign * partial.amount
        if invoice.company_currency_id.is_zero(amount):
            return

        payment = counterpart_line.payment_id or counterpart_line.move_id.origin_payment_id
        if payment and payment.state == "cancel":
            return

        journal = payment.journal_id if payment else counterpart_line.journal_id
        is_actual_payment = bool(payment) or journal.type in ("bank", "cash")
        if is_actual_payment:
            if journal.payment_channel_id:
                column_name = journal.payment_channel_id.name
                used_channel_names.add(column_name)
            else:
                column_name = journal.name
                used_journal_names.add(column_name)
            payment_amounts[invoice.id][column_name] += amount

    def _get_payment_columns(self, payment_data):
        used_channel_names = payment_data["used_channel_names"]
        used_journal_names = payment_data["used_journal_names"]
        active_channels = self.env["account.payment.channel"].search(
            [
                ("active", "=", True),
                ("name", "in", list(used_channel_names)),
            ],
            order="sequence, name",
        )

        columns = []
        seen = set()
        for channel in active_channels:
            if channel.name not in seen:
                columns.append(channel.name)
                seen.add(channel.name)
        for channel_name in sorted(used_channel_names):
            if channel_name not in seen:
                columns.append(channel_name)
                seen.add(channel_name)
        for journal_name in sorted(used_journal_names):
            if journal_name not in seen:
                columns.append(journal_name)
                seen.add(journal_name)
        return columns

    def _format_sale_order_names(self, invoice, sale_orders):
        if sale_orders:
            return ", ".join(sale_orders.mapped("name"))
        return invoice.invoice_origin or ""

    def _get_order_date(self, sale_orders):
        if not sale_orders:
            return False
        return min(sale_orders.mapped("date_order")).date()

    def _get_salesperson(self, invoice, sale_orders):
        if invoice.invoice_user_id:
            return invoice.invoice_user_id.name
        users = sale_orders.mapped("user_id")
        return ", ".join(users.mapped("name"))

    def _get_sales_team(self, invoice, sale_orders):
        if invoice.team_id:
            return invoice.team_id.name
        teams = sale_orders.mapped("team_id")
        return ", ".join(teams.mapped("name"))

    def _get_columns(self, report_data):
        columns = [
            "No.",
            "Order Number",
            "Customer",
            "Order Date",
            "Salesperson",
            "Sales Team",
            "Invoice Number",
            "Invoice Date",
            "Amount Invoiced",
            "Amount Paid",
        ]
        columns += report_data["payment_columns"]
        columns += ["Amount Due"]
        return columns

    def _write_report_header(self, worksheet, formats, last_col):
        generated_at = fields.Datetime.context_timestamp(
            self, fields.Datetime.now()
        ).strftime("%Y-%m-%d %H:%M:%S")
        worksheet.merge_range(0, 0, 0, last_col, self.company_id.name, formats["title"])
        worksheet.merge_range(1, 0, 1, last_col, _("Daily Sales Summary"), formats["title"])
        metadata = [
            (_("From"), self.date_from),
            (_("To"), self.date_to),
            (_("Sales Team"), self.sales_team_id.display_name or _("All")),
            (_("Salesperson"), self.salesperson_id.display_name or _("All")),
            (_("Customer"), self.customer_id.display_name or _("All")),
            (_("Generated Date"), generated_at),
        ]
        for row, (label, value) in enumerate(metadata, start=3):
            worksheet.write(row, 0, label, formats["meta_label"])
            worksheet.write(row, 1, value, formats["meta_value"])

    def _write_detail_row(self, worksheet, formats, row, index, line, report_data):
        invoice = line["invoice"]
        values = [
            index,
            line["order_number"],
            invoice.partner_id.display_name,
            line["order_date"],
            line["salesperson"],
            line["sales_team"],
            invoice.name,
            invoice.invoice_date,
            line["amount_invoiced"],
            line["amount_paid"],
        ]
        col = 0
        for value in values:
            if col in (3, 7) and value:
                worksheet.write_datetime(row, col, value, formats["date"])
            elif col >= 8:
                worksheet.write_number(row, col, value or 0.0, formats["money"])
            elif col == 2:
                worksheet.write(row, col, value or "", formats["text_wrap"])
            else:
                worksheet.write(row, col, value or "", formats["text"])
            col += 1

        for column_name in report_data["payment_columns"]:
            worksheet.write_number(
                row,
                col,
                line["payment_amounts"].get(column_name, 0.0),
                formats["money"],
            )
            col += 1
        worksheet.write_number(row, col, line["amount_due"], formats["money"])

    def _accumulate_totals(self, totals, line, report_data):
        totals["amount_invoiced"] += line["amount_invoiced"]
        totals["amount_paid"] += line["amount_paid"]
        totals["amount_due"] += line["amount_due"]
        for column_name in report_data["payment_columns"]:
            totals["payment_%s" % column_name] += line["payment_amounts"].get(column_name, 0.0)

    def _write_total_row(self, worksheet, formats, row, columns, totals, report_data):
        worksheet.write(row, 0, _("TOTAL"), formats["total_label"])
        numeric_columns = {
            "Amount Invoiced": totals["amount_invoiced"],
            "Amount Paid": totals["amount_paid"],
            "Amount Due": totals["amount_due"],
        }
        for column_name in report_data["payment_columns"]:
            numeric_columns[column_name] = totals["payment_%s" % column_name]

        for col, column_name in enumerate(columns[1:], start=1):
            if column_name in numeric_columns:
                worksheet.write_number(
                    row,
                    col,
                    numeric_columns[column_name],
                    formats["total_money"],
                )
            else:
                worksheet.write_blank(row, col, None, formats["total_label"])

    def _set_column_widths(self, worksheet, columns):
        widths = {
            "No.": 6,
            "Order Number": 18,
            "Customer": 28,
            "Order Date": 13,
            "Salesperson": 18,
            "Sales Team": 18,
            "Invoice Number": 18,
            "Invoice Date": 13,
            "Amount Invoiced": 16,
            "Amount Paid": 16,
            "Amount Due": 14,
        }
        for index, column in enumerate(columns):
            worksheet.set_column(index, index, widths.get(column, 14))

    def _get_xlsx_formats(self, workbook):
        money_format = "#,##0;[Red](#,##0);-"
        return {
            "title": workbook.add_format(
                {
                    "bold": True,
                    "font_size": 15,
                    "align": "center",
                    "valign": "vcenter",
                }
            ),
            "meta_label": workbook.add_format({"bold": True, "align": "left"}),
            "meta_value": workbook.add_format({"align": "left"}),
            "header": workbook.add_format(
                {
                    "bold": True,
                    "align": "center",
                    "valign": "vcenter",
                    "bg_color": "#D9EAF7",
                    "border": 1,
                    "text_wrap": True,
                }
            ),
            "text": workbook.add_format({"valign": "top"}),
            "text_wrap": workbook.add_format({"valign": "top", "text_wrap": True}),
            "date": workbook.add_format({"num_format": "yyyy-mm-dd", "valign": "top"}),
            "money": workbook.add_format(
                {"num_format": money_format, "align": "right", "valign": "top"}
            ),
            "total_label": workbook.add_format(
                {"bold": True, "top": 2, "align": "right", "valign": "vcenter"}
            ),
            "total_money": workbook.add_format(
                {
                    "bold": True,
                    "top": 2,
                    "num_format": money_format,
                    "align": "right",
                    "valign": "vcenter",
                }
            ),
        }

    def _xlsx_filename(self, report_name, date_from, date_to, with_extension=True):
        clean_name = re.sub(r"[^A-Za-z0-9]+", "_", report_name).strip("_")
        filename = "%s_%s_%s" % (
            clean_name,
            date_from.strftime("%Y%m%d"),
            date_to.strftime("%Y%m%d"),
        )
        return "%s.xlsx" % filename if with_extension else filename
