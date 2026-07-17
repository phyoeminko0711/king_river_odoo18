def migrate(cr, version):
    """Prepare the required currency column before the updated model loads."""
    cr.execute(
        """
        ALTER TABLE workshop_job_card
        ADD COLUMN IF NOT EXISTS currency_id integer
        """
    )
    cr.execute(
        """
        UPDATE workshop_job_card AS card
           SET currency_id = company.currency_id
          FROM res_company AS company
         WHERE company.id = 1
           AND card.currency_id IS NULL
        """
    )
    cr.execute(
        """
        UPDATE workshop_job_card AS card
           SET currency_id = fallback.currency_id
          FROM (
                SELECT currency_id
                  FROM res_company
                 WHERE currency_id IS NOT NULL
                 ORDER BY id
                 LIMIT 1
               ) AS fallback
         WHERE card.currency_id IS NULL
        """
    )
