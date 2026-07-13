import json
from odoo import http
from odoo.http import content_disposition, request
from odoo.http import serialize_exception
from odoo.tools import html_escape

class ReportController(http.Controller):

    @http.route('/download/excel', type='http', auth="user")
    def download_excel(self, id, model, report_name='report', **kw):

        report_obj = request.env[model].sudo().browse(int(id))

        try:

            headers = [
                ('Content-Type', 'application/vnd.ms-excel'),
                ('Content-Disposition', content_disposition(report_name + '.xlsx'))
            ]

            response = request.make_response(None, headers=headers)
            report_obj.get_xlsx(response)

            return response

        except Exception as e:

            se = serialize_exception(e)
            error = {
                'code': 200,
                'message': 'Odoo Server Error',
                'data': se}

            return request.make_response(html_escape(json.dumps(error)))