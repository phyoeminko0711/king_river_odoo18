def _column_exists(cr, table_name, column_name):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = %s
           AND column_name = %s
        """,
        (table_name, column_name),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    del version
    cr.execute(
        """
        ALTER TABLE repair_order
        ADD COLUMN IF NOT EXISTS job_card_id integer,
        ADD COLUMN IF NOT EXISTS customer_vehicle_id integer
        """
    )
    cr.execute(
        """
        ALTER TABLE workshop_job_card
        ADD COLUMN IF NOT EXISTS repair_order_id integer
        """
    )

    if _column_exists(cr, "repair_order", "vehicle_id"):
        cr.execute(
            """
            UPDATE repair_order
               SET customer_vehicle_id = vehicle_id
             WHERE customer_vehicle_id IS NULL
               AND vehicle_id IS NOT NULL
            """
        )

    cr.execute(
        """
        UPDATE repair_order AS repair
           SET customer_vehicle_id = card.vehicle_id
          FROM workshop_job_card AS card
         WHERE repair.job_card_id = card.id
           AND repair.customer_vehicle_id IS NULL
        """
    )

    cr.execute(
        """
        UPDATE workshop_job_card AS card
           SET repair_order_id = repair.id,
               state = 'repair_created'
          FROM repair_order AS repair
         WHERE repair.job_card_id = card.id
        """
    )
