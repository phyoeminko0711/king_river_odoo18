# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import date as date_type, datetime, time, timedelta
from io import BytesIO
import re

import pytz
import xlsxwriter

from odoo import fields, models, _
from odoo.tools.float_utils import float_is_zero


class DailyStockSummaryWizard(models.TransientModel):
    _name = "daily.stock.summary.wizard"
    _description = "Daily Stock In Out Summary Excel Wizard"

    date = fields.Date(
        string="Date",
        required=True,
        default=lambda self: fields.Date.context_today(self),
    )
    location_ids = fields.Many2many(
        "stock.location",
        string="Locations",
        domain="[('usage', '=', 'internal'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company.id,
    )

    def print_report(self):
        self.ensure_one()
        report_name = self._xlsx_filename(
            "Daily Stock In Out Summary",
            self.date,
            with_extension=False,
        )
        return {
            "type": "ir.actions.act_url",
            "url": "/download/excel?id=%s&model=%s&report_name=%s"
            % (self.id, self._name, report_name),
            "target": "new",
            "close": True,
        }

    def get_xlsx(self, response):
        self.ensure_one()
        report_data = self._get_report_data()
        excel = BytesIO()
        workbook = xlsxwriter.Workbook(excel, {"in_memory": True})
        worksheet = workbook.add_worksheet(_("Daily Stock Summary")[:31])
        formats = self._get_xlsx_formats(workbook)

        columns = self._get_columns()
        last_col = len(columns) - 1
        self._write_report_header(worksheet, formats, last_col, report_data)

        header_row = 6
        for col, column_name in enumerate(columns):
            worksheet.write(header_row, col, column_name, formats["header"])
        worksheet.set_row(header_row, 30)

        first_data_row = header_row + 1
        row = first_data_row
        for index, line in enumerate(report_data["lines"], start=1):
            self._write_detail_row(worksheet, formats, row, index, line)
            row += 1

        self._write_total_row(
            worksheet,
            formats,
            row,
            first_data_row,
            row - 1,
        )
        worksheet.freeze_panes(first_data_row, 0)
        worksheet.autofilter(header_row, 0, max(row, first_data_row), last_col)
        worksheet.hide_gridlines(2)
        self._set_column_widths(worksheet)

        workbook.close()
        excel.seek(0)
        response.stream.write(excel.read())
        excel.close()

    def _get_report_data(self):
        self.ensure_one()
        locations = self._get_report_locations()
        location_ids = set(locations.ids)
        date_start, date_end = self._get_utc_date_bounds()
        quantities = defaultdict(lambda: defaultdict(float))

        if locations:
            opening_domain = self._base_move_line_domain()
            opening_domain.append(("date", "<", date_start))
            self._add_grouped_quantities(
                quantities,
                "opening_qty",
                opening_domain + [("location_dest_id", "in", locations.ids)],
                "location_dest_id",
            )
            self._add_grouped_quantities(
                quantities,
                "opening_qty",
                opening_domain + [("location_id", "in", locations.ids)],
                "location_id",
                sign=-1.0,
            )

            period_domain = self._base_move_line_domain() + [
                ("date", ">=", date_start),
                ("date", "<", date_end),
            ]
            self._add_grouped_quantities(
                quantities,
                "receipt_in",
                period_domain
                + [
                    ("location_dest_id", "in", locations.ids),
                    ("location_id.usage", "!=", "internal"),
                ],
                "location_dest_id",
            )
            self._add_grouped_quantities(
                quantities,
                "delivery_out",
                period_domain
                + [
                    ("location_id", "in", locations.ids),
                    ("location_dest_id.usage", "!=", "internal"),
                ],
                "location_id",
            )
            self._add_grouped_quantities(
                quantities,
                "internal_in",
                period_domain
                + [
                    ("location_dest_id", "in", locations.ids),
                    ("location_id.usage", "=", "internal"),
                ],
                "location_dest_id",
            )
            self._add_grouped_quantities(
                quantities,
                "internal_out",
                period_domain
                + [
                    ("location_id", "in", locations.ids),
                    ("location_dest_id.usage", "=", "internal"),
                ],
                "location_id",
            )

        product_ids = {key[0] for key in quantities}
        products_by_id = {
            product.id: product
            for product in self.env["product.product"].browse(product_ids).exists()
        }
        locations_by_id = {location.id: location for location in locations}

        lines = []
        for (product_id, location_id), values in quantities.items():
            if location_id not in location_ids or product_id not in products_by_id:
                continue
            product = products_by_id[product_id]
            location = locations_by_id[location_id]
            opening_qty = values["opening_qty"]
            receipt_in = values["receipt_in"]
            delivery_out = values["delivery_out"]
            internal_in = values["internal_in"]
            internal_out = values["internal_out"]
            closing_qty = (
                opening_qty
                + receipt_in
                + internal_in
                - delivery_out
                - internal_out
            )
            if all(
                self._is_zero(product, quantity)
                for quantity in (
                    opening_qty,
                    receipt_in,
                    delivery_out,
                    internal_in,
                    internal_out,
                    closing_qty,
                )
            ):
                continue
            lines.append(
                {
                    "product": product,
                    "engine": product.product_tmpl_id.model_engine or "",
                    "brand": product.brand_id.name or "",
                    "location": location.complete_name,
                    "uom": product.uom_id.name,
                    "opening_qty": opening_qty,
                    "receipt_in": receipt_in,
                    "delivery_out": delivery_out,
                    "internal_in": internal_in,
                    "internal_out": internal_out,
                    "closing_qty": closing_qty,
                }
            )

        lines.sort(
            key=lambda line: (
                (line["product"].name or "").lower(),
                (line["engine"] or "").lower(),
                (line["brand"] or "").lower(),
                (line["location"] or "").lower(),
                line["product"].id,
            )
        )
        return {
            "lines": lines,
            "locations": locations,
        }

    def _get_report_locations(self):
        domain = [
            ("usage", "=", "internal"),
            "|",
            ("company_id", "=", False),
            ("company_id", "=", self.company_id.id),
        ]
        if self.location_ids:
            domain.append(("id", "child_of", self.location_ids.ids))
        return self.env["stock.location"].search(domain, order="complete_name, id")

    def _get_utc_date_bounds(self):
        user_timezone = pytz.timezone(self.env.user.tz or "UTC")
        local_start = user_timezone.localize(datetime.combine(self.date, time.min))
        local_end = local_start + timedelta(days=1)
        return (
            local_start.astimezone(pytz.UTC).replace(tzinfo=None),
            local_end.astimezone(pytz.UTC).replace(tzinfo=None),
        )

    def _base_move_line_domain(self):
        return [
            ("state", "=", "done"),
            ("company_id", "=", self.company_id.id),
            ("product_id", "!=", False),
        ]

    def _add_grouped_quantities(
        self,
        quantities,
        bucket,
        domain,
        location_field,
        sign=1.0,
    ):
        groups = self.env["stock.move.line"].read_group(
            domain,
            ["quantity_product_uom:sum"],
            ["product_id", location_field],
            lazy=False,
        )
        for group in groups:
            product_value = group.get("product_id")
            location_value = group.get(location_field)
            if not product_value or not location_value:
                continue
            key = (product_value[0], location_value[0])
            quantities[key][bucket] += sign * group.get(
                "quantity_product_uom", 0.0
            )

    def _is_zero(self, product, quantity):
        return float_is_zero(
            quantity,
            precision_rounding=product.uom_id.rounding,
        )

    def _get_columns(self):
        return [
            _("No."),
            _("Product"),
            _("Engine"),
            _("Brand"),
            _("Location"),
            _("UoM"),
            _("Opening Qty"),
            _("Receipt In"),
            _("Delivery Out"),
            _("Internal In"),
            _("Internal Out"),
            _("Closing Qty"),
        ]

    def _write_report_header(self, worksheet, formats, last_col, report_data):
        generated_at = fields.Datetime.context_timestamp(
            self, fields.Datetime.now()
        ).strftime("%Y-%m-%d %H:%M:%S")
        selected_location_names = ", ".join(self.location_ids.mapped("complete_name"))
        location_label = selected_location_names or _("All Internal Locations")

        worksheet.merge_range(
            0, 0, 0, last_col, self.company_id.name, formats["company_title"]
        )
        worksheet.merge_range(
            1,
            0,
            1,
            last_col,
            _("Daily Stock In / Out Summary"),
            formats["report_title"],
        )
        metadata = [
            (_("Date"), self.date),
            (_("Locations"), location_label),
            (_("Generated Date"), generated_at),
        ]
        for row, (label, value) in enumerate(metadata, start=3):
            worksheet.write(row, 0, label, formats["meta_label"])
            if isinstance(value, date_type):
                worksheet.write_datetime(row, 1, value, formats["date"])
            else:
                worksheet.merge_range(row, 1, row, last_col, value, formats["meta_value"])

    def _write_detail_row(self, worksheet, formats, row, index, line):
        values = [
            index,
            line["product"].name or "",
            line["engine"],
            line["brand"],
            line["location"],
            line["uom"],
            line["opening_qty"],
            line["receipt_in"],
            line["delivery_out"],
            line["internal_in"],
            line["internal_out"],
        ]
        for col, value in enumerate(values):
            if col == 0:
                worksheet.write_number(row, col, value, formats["center"])
            elif col >= 6:
                worksheet.write_number(row, col, value or 0.0, formats["quantity"])
            elif col in (1, 4):
                worksheet.write(row, col, value or "", formats["text_wrap"])
            else:
                worksheet.write(row, col, value or "", formats["text"])

        excel_row = row + 1
        closing_formula = "=G%d+H%d+J%d-I%d-K%d" % (
            excel_row,
            excel_row,
            excel_row,
            excel_row,
            excel_row,
        )
        worksheet.write_formula(
            row,
            11,
            closing_formula,
            formats["closing_quantity"],
            line["closing_qty"],
        )

    def _write_total_row(self, worksheet, formats, row, first_data_row, last_data_row):
        worksheet.merge_range(row, 0, row, 5, _("TOTAL"), formats["total_label"])
        for col in range(6, 12):
            if last_data_row >= first_data_row:
                column_letter = xlsxwriter.utility.xl_col_to_name(col)
                formula = "=SUM(%s%d:%s%d)" % (
                    column_letter,
                    first_data_row + 1,
                    column_letter,
                    last_data_row + 1,
                )
                worksheet.write_formula(row, col, formula, formats["total_quantity"])
            else:
                worksheet.write_number(row, col, 0.0, formats["total_quantity"])

    def _set_column_widths(self, worksheet):
        widths = [6, 30, 20, 16, 32, 12, 14, 14, 14, 14, 14, 14]
        for index, width in enumerate(widths):
            worksheet.set_column(index, index, width)

    def _get_xlsx_formats(self, workbook):
        quantity_format = "#,##0.00;[Red](#,##0.00);-"
        border_color = "#B8C2CC"
        return {
            "company_title": workbook.add_format(
                {
                    "bold": True,
                    "font_size": 15,
                    "align": "center",
                    "valign": "vcenter",
                }
            ),
            "report_title": workbook.add_format(
                {
                    "bold": True,
                    "font_size": 13,
                    "font_color": "#FFFFFF",
                    "bg_color": "#273C89",
                    "align": "center",
                    "valign": "vcenter",
                }
            ),
            "meta_label": workbook.add_format(
                {"bold": True, "bg_color": "#E8ECF4", "border": 1}
            ),
            "meta_value": workbook.add_format({"align": "left"}),
            "date": workbook.add_format(
                {"num_format": "yyyy-mm-dd", "align": "left"}
            ),
            "header": workbook.add_format(
                {
                    "bold": True,
                    "font_color": "#FFFFFF",
                    "bg_color": "#273C89",
                    "border": 1,
                    "border_color": border_color,
                    "align": "center",
                    "valign": "vcenter",
                    "text_wrap": True,
                }
            ),
            "center": workbook.add_format(
                {"border": 1, "border_color": border_color, "align": "center"}
            ),
            "text": workbook.add_format(
                {"border": 1, "border_color": border_color, "valign": "top"}
            ),
            "text_wrap": workbook.add_format(
                {
                    "border": 1,
                    "border_color": border_color,
                    "valign": "top",
                    "text_wrap": True,
                }
            ),
            "quantity": workbook.add_format(
                {
                    "border": 1,
                    "border_color": border_color,
                    "num_format": quantity_format,
                    "align": "right",
                }
            ),
            "closing_quantity": workbook.add_format(
                {
                    "bold": True,
                    "border": 1,
                    "border_color": border_color,
                    "bg_color": "#E8F3E8",
                    "num_format": quantity_format,
                    "align": "right",
                }
            ),
            "total_label": workbook.add_format(
                {
                    "bold": True,
                    "top": 2,
                    "align": "right",
                    "valign": "vcenter",
                }
            ),
            "total_quantity": workbook.add_format(
                {
                    "bold": True,
                    "top": 2,
                    "num_format": quantity_format,
                    "align": "right",
                }
            ),
        }

    def _xlsx_filename(self, report_name, report_date, with_extension=True):
        clean_name = re.sub(r"[^A-Za-z0-9]+", "_", report_name).strip("_")
        filename = "%s_%s" % (clean_name, report_date.strftime("%Y%m%d"))
        return "%s.xlsx" % filename if with_extension else filename
