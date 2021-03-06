# -*- coding: utf-8 -*-
{
    'name': "Quemen",

    'summary': """ Desarrollo extra quemen """,

    'description': """
        Desarrollo extra pra quemen
    """,

    'author': "JS",
    'website': "",

    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['stock','base','point_of_sale','hr_payroll'],

    'data': [
        'data/paperformat_ticket.xml',
        # 'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/report.xml',
        'views/vale_retiro.xml',
        'views/templates.xml',
        'views/reporte_codigo_barras.xml',
        'views/reporte_salidas.xml',
        'views/pos_box.xml',
        'views/reporte_entrega_valores.xml',
        'data/quemen_data.xml',
        'views/quemen_views.xml',
        'views/stock_quant_views.xml',
        'views/pos_session_view.xml',
        'views/pos_config_view.xml',
        'wizard/reporte_entrega_valores_wizard.xml',
        'views/reloj_checador_wizard.xml',
        'views/hr_views.xml',
        'views/res_users_view.xml',
        'wizard/reporte_productos_labor_venta_wizard.xml',
        'views/reporte_productos_labor_venta.xml',
        'views/reporte_existencias.xml',
        'wizard/reporte_existencias_wizard.xml',
        'views/stock_picking_views.xml',
        'views/reporte_formato_salidas.xml',
        'views/reporte_salidas.xml',
        'wizard/reporte_salidas_wizard.xml',
        'wizard/reporte_formato_salidas_wizard.xml',
        'views/report_quemen.xml',
        'views/reportes_retiro_view.xml',
        'views/reporte_retiros_sesion.xml',
        'views/product_template_extra_fields_views.xml'

    ],
    'qweb': [
        'static/src/xml/pos.xml',
    ],
}
