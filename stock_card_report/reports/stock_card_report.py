# Copyright 2019 Ecosoft Co., Ltd. (http://ecosoft.co.th)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockCardView(models.TransientModel):
    _name = "stock.card.view"
    _description = "Stock Card View"
    _order = "date"

    date = fields.Datetime()
    product_id = fields.Many2one(comodel_name="product.product")
    product_qty = fields.Float()
    product_uom_qty = fields.Float()
    product_uom = fields.Many2one(comodel_name="uom.uom")
    reference = fields.Char()
    location_id = fields.Many2one(comodel_name="stock.location")
    location_dest_id = fields.Many2one(comodel_name="stock.location")
    is_initial = fields.Boolean()
    product_in = fields.Float()
    product_out = fields.Float()
    picking_id = fields.Many2one(comodel_name="stock.picking")
    ##############
    value = fields.Float()
    category_id = fields.Many2one(comodel_name="product.category")
    ################

    def name_get(self):
        result = []
        for rec in self:
            name = rec.reference
            if rec.picking_id.origin:
                name = "{} ({})".format(name, rec.picking_id.origin)
            result.append((rec.id, name))
        return result


class StockCardReport(models.TransientModel):
    _name = "report.stock.card.report"
    _description = "Stock Card Report"

    # Filters fields, used for data computation
    date_from = fields.Date()
    date_to = fields.Date()
    product_ids = fields.Many2many(comodel_name="product.product")
    location_ids = fields.Many2many(comodel_name="stock.location")
    #######################
    company_id = fields.Many2one('res.company')
    category_id = fields.Many2one(comodel_name="product.category")
    check_no_move = fields.Boolean(string="Include no move in period")
    #########################

    def _compute_results(self):
        self.ensure_one()
        date_from = self.date_from or "0001-01-01"
        self.date_to = self.date_to or fields.Date.context_today(self)
        if self.location_ids:
            location_ids = self.location_ids
        else:
            location_ids = self.env['stock.location'].search([ '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id), ('usage', '=', 'internal')])

        locations = self.env["stock.location"].search([("id", "child_of", location_ids.ids)])

        self._cr.execute(
            """
            WITH product_move AS
            ( SELECT sml.date, sml.product_id, sml.quantity as product_qty, 
                coalesce(case when sml.lot_name is not null then sml.lot_name else lot.name end, '') serial_no, 
                sml.reference, sml.location_id, sml.location_dest_id, sml.picking_id,
                coalesce(case when sml.location_dest_id in %s then sml.quantity end, 0) as product_in,
                coalesce(case when sml.location_id in %s then sml.quantity end, 0) as product_out,
                case when sml.date < %s then True else False end as is_initial,
                coalesce((select case when quantity <> 0 then value/quantity else 0 end as value from (select sum(value) as value, sum(quantity) as quantity from stock_valuation_layer where stock_move_id=sml.move_id) valuation), 0) as value,
                CASE WHEN ld.usage = 'internal' THEN ld.complete_name ELSE '' END AS destination,
                CASE WHEN ls.usage = 'internal' THEN ls.complete_name ELSE '' END AS source
              FROM stock_move_line sml
              LEFT JOIN stock_lot lot ON lot.id = sml.lot_id
              LEFT JOIN stock_location ls ON ls.id = sml.location_id
              LEFT JOIN stock_location ld ON ld.id = sml.location_dest_id
              WHERE (sml.location_id in %s or sml.location_dest_id in %s)
                and sml.state = 'done' and sml.product_id in %s
                and CAST(sml.date AS date) <= %s
              ORDER BY sml.date, sml.reference
            )
            SELECT date, product_id, sum(product_qty) as product_qty, serial_no,
                reference, location_id, location_dest_id, picking_id, is_initial, 
                sum(product_in) as product_in, sum(product_out) as product_out, sum(value) as value, source, destination
            FROM product_move
            GROUP BY date, product_id, serial_no, reference, location_id, location_dest_id, picking_id, is_initial, source, destination
            ORDER BY product_id, date, reference
        """,
            (
                tuple(locations.ids),
                tuple(locations.ids),
                date_from,
                tuple(locations.ids),
                tuple(locations.ids),
                tuple(self.product_ids.ids),
                self.date_to,
            ),
        )
        stock_card_results = self._cr.dictfetchall()
        prev = None
        stock_card_dict = {}

        for line in stock_card_results:
            if not prev or line['product_id'] != prev:
                prev = line['product_id']
                stock_card_dict.update({line['product_id']: {}})
                balance = (line['product_in'] - line['product_out']) if line['is_initial'] else 0
                ending_balance_value = (line['value'] * balance) if line['is_initial'] else 0
                product_lines = []
                if not line['is_initial']:
                    product_lines.append(line)

                # product_full_name = self.env['product.product'].browse(line['product_id']).name_get()[0][1]
                product_full_name = self.env['product.product'].browse(line['product_id']).display_name
                stock_card_dict[line['product_id']] = {'name': product_full_name, 'balance': balance,
                                                       'ending_balance_value': ending_balance_value,
                                                       'product_lines': product_lines}
            else:
                if line['is_initial']:
                    stock_card_dict[line['product_id']]['balance'] += (line['product_in'] - line['product_out'])
                    stock_card_dict[line['product_id']]['ending_balance_value'] += (line['value'] * (line['product_in'] - line['product_out']))
                else:
                    stock_card_dict[line['product_id']]['product_lines'].append(line)
        return stock_card_dict

    ########################
    def print_report(self, report_type="qweb"):
        self.ensure_one()
        action = (
            report_type == "xlsx"
            and self.env.ref("stock_card_report.action_stock_card_report_xlsx")
            or self.env.ref("stock_card_report.action_stock_card_report_pdf")
        )
        return action.report_action(self, config=False)

    def _get_html(self):
        result = {}
        rcontext = {}
        report = self.browse(self._context.get("active_id"))
        if report:
            rcontext["o"] = report
            result['html'] = self.env['ir.qweb']._render('stock_card_report.report_stock_card_report_html', rcontext)
        return result

    @api.model
    def get_html(self, given_context=None):
        return self.with_context(given_context)._get_html()
