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
        ALTER TABLE workshop_job_card_option
        ADD COLUMN IF NOT EXISTS job_card_id integer
        """
    )
    cr.execute(
        """
        UPDATE workshop_job_card_option AS option
           SET job_card_id = service.job_card_id
          FROM workshop_job_card_service AS service
         WHERE option.service_id = service.id
           AND option.job_card_id IS NULL
        """
    )
    _drop_not_null_if_present(cr, "workshop_job_card_option", "service_id")
