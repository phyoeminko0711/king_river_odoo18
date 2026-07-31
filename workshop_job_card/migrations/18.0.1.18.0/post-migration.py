from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    yes_no = env.ref("workshop_job_card.inspection_result_type_yes_no", raise_if_not_found=False)
    yes = env.ref("workshop_job_card.inspection_result_option_yes", raise_if_not_found=False)
    no = env.ref("workshop_job_card.inspection_result_option_no", raise_if_not_found=False)
    ok = env.ref("workshop_job_card.inspection_result_option_ok", raise_if_not_found=False)
    ng = env.ref("workshop_job_card.inspection_result_option_ng", raise_if_not_found=False)
    na = env.ref("workshop_job_card.inspection_result_option_na", raise_if_not_found=False)
    if yes_no and yes and no:
        cr.execute(
            """
            SELECT column_name
              FROM information_schema.columns
             WHERE table_name = 'workshop_inspection_template_line'
               AND column_name = 'default_result'
            """
        )
        if cr.fetchone():
            cr.execute(
                """
                UPDATE workshop_inspection_template_line
                   SET result_type_id = %s,
                       default_result_option_id = CASE
                           WHEN default_result IN ('yes', 'ok') THEN %s
                           WHEN default_result IN ('no', 'ng', 'na') THEN %s
                           ELSE %s
                       END
                 WHERE result_type_id IS NULL
                """,
                (yes_no.id, yes.id, no.id, yes.id),
            )
        cr.execute(
            """
            UPDATE workshop_inspection_template_line
               SET result_type_id = %s
             WHERE result_type_id IS NULL
            """,
            (yes_no.id,),
        )
    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_name = 'workshop_job_card_inspection_line'
           AND column_name = 'result'
        """
    )
    if cr.fetchone():
        cr.execute(
            """
            UPDATE workshop_job_card_inspection_line
               SET result_name = CASE
                   WHEN result = 'yes' THEN 'Yes'
                   WHEN result = 'no' THEN 'No'
                   WHEN result = 'ok' THEN 'OK'
                   WHEN result = 'ng' THEN 'NG'
                   WHEN result = 'na' THEN 'N/A'
                   ELSE result
               END
             WHERE result_name IS NULL
               AND result IS NOT NULL
            """
        )
        mappings = [
            ("yes", yes),
            ("no", no),
            ("ok", ok),
            ("ng", ng),
            ("na", na),
        ]
        for code, option in mappings:
            if option:
                cr.execute(
                    """
                    UPDATE workshop_job_card_inspection_line
                       SET result_option_id = %s
                     WHERE result_option_id IS NULL
                       AND result = %s
                    """,
                    (option.id, code),
                )
