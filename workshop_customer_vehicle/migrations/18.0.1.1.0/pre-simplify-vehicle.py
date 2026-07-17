"""Remove the retired global chassis-number uniqueness constraint."""

from psycopg2 import sql


def migrate(cr, version):
    cr.execute(
        """
        SELECT conname
          FROM pg_constraint
         WHERE conrelid = 'workshop_customer_vehicle'::regclass
           AND conname LIKE '%%chassis_unique%%'
        """
    )
    for (constraint_name,) in cr.fetchall():
        cr.execute(
            sql.SQL("ALTER TABLE workshop_customer_vehicle DROP CONSTRAINT {}").format(
                sql.Identifier(constraint_name)
            )
        )

