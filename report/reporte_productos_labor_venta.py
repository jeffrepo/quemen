# -*- encoding: utf-8 -*-

from odoo import api, models, fields
from datetime import date, timedelta
import datetime
import time
import dateutil.parser
from dateutil.relativedelta import relativedelta
from dateutil import relativedelta as rdelta
from odoo.fields import Date, Datetime
import logging
from operator import itemgetter
import pytz
# import odoo.addons.hr_gt.a_letras

class ReportProductosLaborVenta(models.AbstractModel):
    _name = 'report.quemen.reporte_productos_labor_venta'
    _description = " "

    def productos_vencimiento(self, tienda_id):
        logging.warning('tienda')
        logging.warning(tienda_id)
        tienda_id = self.env['pos.config'].search([('id','=',tienda_id[0])])
        ubicacion_id = tienda_id.picking_type_id.default_location_src_id
        stock_id = self.env['stock.quant'].search([('location_id','=',ubicacion_id.id),('lot_id','!=', False),('quantity','>',0)], order='product_id asc')
        inventario = []
        if stock_id:
            fecha = self.fecha()
            for producto in stock_id:
                if producto.lot_id and producto.lot_id.expiration_date and str(producto.lot_id.expiration_date.strftime('%Y-%m-%d')) == str(fecha):
                    inventario.append(producto)
        logging.warn(inventario)
        return inventario

    def fecha(self):
        timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz or 'UTC')
        fecha_hoy = datetime.datetime.now().astimezone(timezone).date()
        fecha_hoy = datetime.datetime.strptime(str(fecha_hoy),'%Y-%m-%d') + timedelta(days = 1)
        logging.warning(fecha_hoy.date())
        return fecha_hoy.date()

    def fecha_hora_actual(self):
        timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz or 'UTC')
        fecha_hora = datetime.datetime.now().astimezone(timezone).strftime('%d/%m/%Y %H:%M:%S')
        return fecha_hora

    def obtener_tienda(self, tienda_id):
        tienda = self.env['pos.config'].search([('id','=',tienda_id[0])])
        return tienda;

    @api.model
    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_ids', []))
        tienda_id = data['form']['tienda_id']
        # fecha = data['form']['fecha']
        logging.warning(tienda_id)
        return {
            'data': data['form'],
            'docs': docs,
            'productos_vencimiento': self.productos_vencimiento,
            'fecha_hora_actual': self.fecha_hora_actual,
            'obtener_tienda': self.obtener_tienda,
            'tienda': tienda_id,
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
