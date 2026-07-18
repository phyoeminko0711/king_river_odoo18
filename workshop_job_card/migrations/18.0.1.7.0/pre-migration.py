def _table_exists(cr, table_name):
    cr.execute("SELECT to_regclass(%s)", (table_name,))
    return bool(cr.fetchone()[0])


def migrate(cr, version):
    del version
    required_tables = {
        "workshop_job_card_line",
        "workshop_job_card_service",
        "workshop_repair_service",
    }
    if not all(_table_exists(cr, table_name) for table_name in required_tables):
        return

    cr.execute(
        """
        ALTER TABLE workshop_job_card_line
            ADD COLUMN IF NOT EXISTS job_card_service_id integer,
            ADD COLUMN IF NOT EXISTS repair_service_id integer
        """
    )

    # Create masters for text-only lines written before job_card_service_id
    # became mandatory.
    cr.execute(
        """
        INSERT INTO workshop_repair_service
                    (name, active, sequence, create_uid, write_uid,
                     create_date, write_date)
        SELECT source.name, TRUE, 10, 1, 1, NOW(), NOW()
          FROM (
                SELECT DISTINCT btrim(repair_service) AS name
                  FROM workshop_job_card_line
                 WHERE job_card_service_id IS NULL
                   AND NULLIF(btrim(repair_service), '') IS NOT NULL
               ) AS source
         WHERE NOT EXISTS (
                SELECT 1
                  FROM workshop_repair_service AS master
                 WHERE lower(btrim(master.name)) = lower(source.name)
               )
        """
    )

    cr.execute(
        """
        INSERT INTO workshop_job_card_service
                    (job_card_id, repair_service_id, sequence, name,
                     create_uid, write_uid, create_date, write_date)
        SELECT DISTINCT line.job_card_id, master.id, 10, master.name,
                        1, 1, NOW(), NOW()
          FROM workshop_job_card_line AS line
          JOIN workshop_repair_service AS master
            ON lower(btrim(master.name)) = lower(btrim(line.repair_service))
         WHERE line.job_card_service_id IS NULL
           AND NOT EXISTS (
                SELECT 1
                  FROM workshop_job_card_service AS existing
                 WHERE existing.job_card_id = line.job_card_id
                   AND existing.repair_service_id = master.id
           )
        """
    )

    cr.execute(
        """
        UPDATE workshop_job_card_line AS line
           SET job_card_service_id = service_line.id,
               repair_service_id = service_line.repair_service_id
          FROM workshop_job_card_service AS service_line
          JOIN workshop_repair_service AS master
            ON master.id = service_line.repair_service_id
         WHERE line.job_card_service_id IS NULL
           AND service_line.job_card_id = line.job_card_id
           AND lower(btrim(master.name)) = lower(btrim(line.repair_service))
        """
    )

    # Extremely old or malformed rows without service text receive a dedicated
    # compatibility master rather than being deleted.
    cr.execute(
        """
        INSERT INTO workshop_repair_service
                    (name, active, sequence, create_uid, write_uid,
                     create_date, write_date)
        SELECT 'Legacy Repair Option ' || line.id,
               TRUE, 10, 1, 1, NOW(), NOW()
          FROM workshop_job_card_line AS line
         WHERE line.job_card_service_id IS NULL
        """
    )
    cr.execute(
        """
        INSERT INTO workshop_job_card_service
                    (job_card_id, repair_service_id, sequence, name,
                     create_uid, write_uid, create_date, write_date)
        SELECT line.job_card_id, master.id, 10, master.name,
               1, 1, NOW(), NOW()
          FROM workshop_job_card_line AS line
          JOIN workshop_repair_service AS master
            ON master.name = 'Legacy Repair Option ' || line.id
         WHERE line.job_card_service_id IS NULL
        """
    )
    cr.execute(
        """
        UPDATE workshop_job_card_line AS line
           SET job_card_service_id = service_line.id,
               repair_service_id = service_line.repair_service_id
          FROM workshop_job_card_service AS service_line
          JOIN workshop_repair_service AS master
            ON master.id = service_line.repair_service_id
         WHERE line.job_card_service_id IS NULL
           AND service_line.job_card_id = line.job_card_id
           AND master.name = 'Legacy Repair Option ' || line.id
        """
    )

    cr.execute(
        """
        UPDATE workshop_job_card_line AS line
           SET job_card_id = service_line.job_card_id,
               repair_service_id = service_line.repair_service_id,
               repair_service = master.name
          FROM workshop_job_card_service AS service_line
          JOIN workshop_repair_service AS master
            ON master.id = service_line.repair_service_id
         WHERE line.job_card_service_id = service_line.id
        """
    )
