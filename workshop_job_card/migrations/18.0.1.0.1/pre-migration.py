"""Remove legacy custom-group links before Odoo deletes obsolete groups."""


LEGACY_GROUP_XMLIDS = (
    "group_job_card_user",
    "group_job_card_manager",
    "group_job_card_administrator",
)

def migrate(cr, version):
    """Release legacy Job Card group foreign keys."""
    cr.execute(
        """
        SELECT res_id
          FROM ir_model_data
         WHERE module = 'workshop_job_card'
           AND model = 'res.groups'
           AND name IN %s
        """,
        [LEGACY_GROUP_XMLIDS],
    )
    legacy_group_ids = [row[0] for row in cr.fetchall()]

    if legacy_group_ids:
        legacy_ids = tuple(legacy_group_ids)
        cr.execute(
            "DELETE FROM rule_group_rel WHERE group_id IN %s",
            [legacy_ids],
        )
        cr.execute(
            "DELETE FROM res_groups_users_rel WHERE gid IN %s",
            [legacy_ids],
        )
        cr.execute(
            "DELETE FROM res_groups_implied_rel WHERE gid IN %s OR hid IN %s",
            [legacy_ids, legacy_ids],
        )
        cr.execute(
            "DELETE FROM ir_ui_menu_group_rel WHERE gid IN %s",
            [legacy_ids],
        )
        cr.execute(
            "DELETE FROM ir_ui_view_group_rel WHERE group_id IN %s",
            [legacy_ids],
        )
        cr.execute(
            "DELETE FROM ir_model_access WHERE group_id IN %s",
            [legacy_ids],
        )
