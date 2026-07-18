def _table_exists(cr, table_name):
    cr.execute("SELECT to_regclass(%s)", (table_name,))
    return bool(cr.fetchone()[0])


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
    if not _table_exists(cr, "workshop_job_card_service"):
        return

    cr.execute(
        """
        ALTER TABLE workshop_job_card_service
            ADD COLUMN IF NOT EXISTS sequence integer DEFAULT 10,
            ADD COLUMN IF NOT EXISTS repair_service_id integer
        """
    )
    cr.execute(
        """
        ALTER TABLE workshop_job_card_service
        ALTER COLUMN name DROP NOT NULL
        """
    )

    if _table_exists(cr, "workshop_job_card_line"):
        cr.execute(
            """
            ALTER TABLE workshop_job_card_line
            ADD COLUMN IF NOT EXISTS job_card_service_id integer
            """
        )

    if not _table_exists(cr, "workshop_repair_service"):
        return

    line_source = ""
    if _table_exists(cr, "workshop_job_card_line"):
        line_source = """
            UNION
            SELECT DISTINCT btrim(repair_service)
              FROM workshop_job_card_line
             WHERE NULLIF(btrim(repair_service), '') IS NOT NULL
        """

    cr.execute(
        f"""
        INSERT INTO workshop_repair_service
                    (name, active, sequence, create_uid, write_uid,
                     create_date, write_date)
        SELECT source.name, TRUE, 10, 1, 1, NOW(), NOW()
          FROM (
                SELECT DISTINCT btrim(name) AS name
                  FROM workshop_job_card_service
                 WHERE NULLIF(btrim(name), '') IS NOT NULL
                {line_source}
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
        UPDATE workshop_job_card_service AS service_line
           SET repair_service_id = master.id,
               sequence = COALESCE(service_line.sequence, 10)
          FROM workshop_repair_service AS master
         WHERE service_line.repair_service_id IS NULL
           AND NULLIF(btrim(service_line.name), '') IS NOT NULL
           AND lower(btrim(master.name)) = lower(btrim(service_line.name))
        """
    )

    cr.execute(
        """
        INSERT INTO workshop_repair_service
                    (name, active, sequence, create_uid, write_uid,
                     create_date, write_date)
        SELECT 'Legacy Repair Service ' || service_line.id,
               TRUE, 10, 1, 1, NOW(), NOW()
          FROM workshop_job_card_service AS service_line
         WHERE service_line.repair_service_id IS NULL
        """
    )
    cr.execute(
        """
        UPDATE workshop_job_card_service AS service_line
           SET repair_service_id = master.id,
               name = COALESCE(
                   NULLIF(btrim(service_line.name), ''),
                   master.name
               )
          FROM workshop_repair_service AS master
         WHERE service_line.repair_service_id IS NULL
           AND master.name = 'Legacy Repair Service ' || service_line.id
        """
    )

    # Collapse duplicate legacy service headers before the new unique
    # constraint is installed. Legacy option records continue to point to the
    # retained header.
    cr.execute(
        """
        CREATE TEMP TABLE workshop_service_duplicate_map ON COMMIT DROP AS
        SELECT duplicate.id AS duplicate_id, keeper.id AS keeper_id
          FROM workshop_job_card_service AS duplicate
          JOIN workshop_job_card_service AS keeper
            ON keeper.job_card_id = duplicate.job_card_id
           AND keeper.repair_service_id = duplicate.repair_service_id
           AND keeper.id = (
                SELECT MIN(candidate.id)
                  FROM workshop_job_card_service AS candidate
                 WHERE candidate.job_card_id = duplicate.job_card_id
                   AND candidate.repair_service_id = duplicate.repair_service_id
           )
         WHERE duplicate.id != keeper.id
        """
    )
    if _column_exists(cr, "workshop_job_card_option", "service_id"):
        cr.execute(
            """
            UPDATE workshop_job_card_option AS option
               SET service_id = mapping.keeper_id
              FROM workshop_service_duplicate_map AS mapping
             WHERE option.service_id = mapping.duplicate_id
            """
        )
    if _table_exists(cr, "workshop_job_card_line"):
        cr.execute(
            """
            UPDATE workshop_job_card_line AS line
               SET job_card_service_id = mapping.keeper_id
              FROM workshop_service_duplicate_map AS mapping
             WHERE line.job_card_service_id = mapping.duplicate_id
            """
        )
    cr.execute(
        """
        DELETE FROM workshop_job_card_service AS service_line
         USING workshop_service_duplicate_map AS mapping
         WHERE service_line.id = mapping.duplicate_id
        """
    )

    if _table_exists(cr, "workshop_job_card_line"):
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
               SET job_card_service_id = service_line.id
              FROM workshop_job_card_service AS service_line
              JOIN workshop_repair_service AS master
                ON master.id = service_line.repair_service_id
             WHERE line.job_card_service_id IS NULL
               AND service_line.job_card_id = line.job_card_id
               AND lower(btrim(master.name)) = lower(btrim(line.repair_service))
            """
        )
