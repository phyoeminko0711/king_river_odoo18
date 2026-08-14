import base64

from odoo import fields, http
from odoo.http import content_disposition, request


class WorkshopJobCardShareController(http.Controller):
    @http.route(
        "/job_card/share/<string:token>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def share_job_card_pdf(self, token, download=False, **kwargs):
        job_card = request.env["workshop.job.card"].sudo().search(
            [("viber_share_token", "=", token)],
            limit=1,
        )
        if (
            not job_card
            or not job_card.viber_share_attachment_id
            or not job_card.viber_share_token_expiry
            or job_card.viber_share_token_expiry <= fields.Datetime.now()
        ):
            return request.not_found()

        attachment = job_card.viber_share_attachment_id.sudo()
        pdf_content = base64.b64decode(attachment.datas or b"")
        if download:
            disposition = content_disposition(attachment.name)
        else:
            filename = (attachment.name or "Job_Card.pdf").replace('"', "")
            disposition = 'inline; filename="%s"' % filename
        headers = [
            ("Content-Type", "application/pdf"),
            ("Content-Length", str(len(pdf_content))),
            ("Content-Disposition", disposition),
            ("Cache-Control", "private, no-store, max-age=0"),
            ("X-Content-Type-Options", "nosniff"),
        ]
        return request.make_response(pdf_content, headers=headers)
