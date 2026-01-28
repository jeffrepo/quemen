from odoo.upgrade import util

def migrate(cr, version):

    cr.execute("""
        INSERT INTO ir_config_parameter (key, value, create_date, write_date)
        VALUES ('quemen.pre17_migration_ran', now()::text, now(), now())
        ON CONFLICT (key) DO UPDATE SET value = excluded.value, write_date = now()
    """)

    # sms.sms: evitar operaciones costosas en tablas grandes
    util.alter_column_type(cr, "sms_sms", "uuid", "varchar")
    util.create_column(cr, "sms_sms", "to_delete", "bool", default=False)


    # 1) Crear columnas para que Odoo 17 NO intente computarlas por ORM sobre 3.4M registros
    util.create_column(cr, "pos_order", "l10n_mx_edi_cfdi_attachment_id", "int4")
    util.create_column(cr, "pos_order", "l10n_mx_edi_cfdi_state", "varchar")
    util.create_column(cr, "pos_order", "l10n_mx_edi_cfdi_sat_state", "varchar")
    util.create_column(cr, "pos_order", "l10n_mx_edi_cfdi_uuid", "varchar")
    util.create_column(cr, "pos_order", "l10n_mx_edi_is_cfdi_needed", "bool")
    util.create_column(cr, "pos_order", "l10n_mx_edi_cfdi_to_public", "bool")
    # config_id (stored compute nuevo)
    util.create_column(cr, "pos_order", "config_id", "int4")

    # stored con default
    util.create_column(cr, "pos_order", "l10n_mx_edi_usage", "varchar", default="G03")

    # Primero: usar el campo legacy que ya existe en tu BD
    util.explode_execute(cr, """
        UPDATE pos_order
          SET config_id = x_config_id_stored
        WHERE config_id IS NULL
          AND x_config_id_stored IS NOT NULL
    """)

    # Fallback: por sesión
    util.explode_execute(cr, """
        UPDATE pos_order p
          SET config_id = s.config_id
          FROM pos_session s
        WHERE p.config_id IS NULL
          AND p.session_id = s.id
          AND s.config_id IS NOT NULL
    """)




    # 2) Poblar l10n_mx_edi_usage desde account_move (tu v15 sí lo tiene)
    util.explode_execute(cr, """
        UPDATE pos_order p
           SET l10n_mx_edi_usage = COALESCE(m.l10n_mx_edi_usage, 'G03')
          FROM account_move m
         WHERE p.account_move = m.id
           AND p.account_move IS NOT NULL
           AND (p.l10n_mx_edi_usage IS NULL OR p.l10n_mx_edi_usage = '')
    """)

    # 3) Poblar SAT status (tu v15 tiene l10n_mx_edi_sat_status)
    util.explode_execute(cr, """
        UPDATE pos_order p
           SET l10n_mx_edi_cfdi_sat_state = m.l10n_mx_edi_sat_status
          FROM account_move m
         WHERE p.account_move = m.id
           AND p.account_move IS NOT NULL
           AND p.l10n_mx_edi_cfdi_sat_state IS NULL
    """)

    # 4) Marcar "is_cfdi_needed" para órdenes con factura ligada (conservador)
    util.explode_execute(cr, """
        UPDATE pos_order p
           SET l10n_mx_edi_is_cfdi_needed = TRUE
         WHERE p.account_move IS NOT NULL
           AND p.l10n_mx_edi_is_cfdi_needed IS NULL
    """)

    # 5) Intentar setear attachment XML CFDI desde ir_attachment del account.move (más seguro que ORM)
    util.explode_execute(cr, """
        WITH xml_att AS (
          SELECT DISTINCT ON (a.res_id)
                 a.res_id AS move_id,
                 a.id     AS attachment_id
            FROM ir_attachment a
           WHERE a.res_model = 'account.move'
             AND (a.mimetype IN ('application/xml','text/xml') OR lower(a.name) LIKE '%.xml')
           ORDER BY a.res_id, a.create_date DESC NULLS LAST, a.id DESC
        )
        UPDATE pos_order p
           SET l10n_mx_edi_cfdi_attachment_id = x.attachment_id
          FROM xml_att x
         WHERE p.account_move = x.move_id
           AND p.l10n_mx_edi_cfdi_attachment_id IS NULL
    """)