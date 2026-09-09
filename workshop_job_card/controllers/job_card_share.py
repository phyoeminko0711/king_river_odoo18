from odoo import fields, http
from odoo.http import request


class WorkshopJobCardShareController(http.Controller):
    @http.route(
        "/job_card/share/<string:token>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def share_job_card_report(self, token, download=False, **kwargs):
        job_card = request.env["workshop.job.card"].sudo().search(
            [("viber_share_token", "=", token)],
            limit=1,
        )
        if (
            not job_card
            or not job_card.viber_share_token_expiry
            or job_card.viber_share_token_expiry <= fields.Datetime.now()
        ):
            return request.not_found()

        html = request.env["ir.actions.report"].sudo()._render_qweb_html(
            "workshop_job_card.report_workshop_job_card_document",
            [job_card.id],
        )[0]
        headers = [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Cache-Control", "private, no-store, max-age=0"),
            ("X-Content-Type-Options", "nosniff"),
        ]
        return request.make_response(html, headers=headers)
