from psycopg2 import sql


def _drop_not_null_if_present(cr, table_name, column_name):
    cr.execute(
        """
        SELECT is_nullable
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = %s
           AND column_name = %s
        """,
        (table_name, column_name),
    )
    column = cr.fetchone()
    if column and column[0] == "NO":
        cr.execute(
            sql.SQL("ALTER TABLE {} ALTER COLUMN {} DROP NOT NULL").format(
                sql.Identifier(table_name), sql.Identifier(column_name)
            )
        )


def migrate(cr, version):
    del version
    cr.execute(
        """
        UPDATE workshop_job_card
           SET state = 'draft'
         WHERE state IS NULL
            OR state NOT IN (
                'draft', 'sent', 'approved', 'repair_created', 'rejected', 'cancelled'
            )
        """
    )

    for table_name, column_name in (
        ("workshop_job_card", "currency_id"),
        ("workshop_job_card_option", "product_id"),
        ("workshop_job_card_option", "quantity"),
        ("workshop_job_card_option", "product_uom_id"),
        ("workshop_job_card_option", "unit_price"),
    ):
        _drop_not_null_if_present(cr, table_name, column_name)
