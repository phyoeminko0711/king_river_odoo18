from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Copy legacy flat option rows into the new direct-entry option table."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    JobCard = env["workshop.job.card"]
    LegacyOption = env["workshop.job.card.option"]
    NewLine = env["workshop.job.card.line"].with_context(
        skip_job_card_state_check=True
    )

    for card in JobCard.search([]):
        if card.line_ids:
            continue
        legacy_lines = LegacyOption.search(
            [("job_card_id", "=", card.id)], order="id"
        )
        for legacy in legacy_lines.filtered("product_id"):
            product = legacy.product_id
            service_name = "Legacy Repair Option"
            if "service_id" in legacy._fields and legacy.service_id:
                service_name = legacy.service_id.display_name
            NewLine.create(
                {
                    "job_card_id": card.id,
                    "repair_service": service_name,
                    "product_id": product.id,
                    "quantity": legacy.quantity or 1.0,
                    "product_uom_id": product.uom_id.id,
                    "unit_price": product.lst_price,
                    "selected": legacy.selected,
                }
            )
