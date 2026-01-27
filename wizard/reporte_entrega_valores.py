# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import time
import base64
import xlsxwriter
import io
import logging
from datetime import date, timedelta
import datetime
import dateutil.parser
from dateutil.relativedelta import relativedelta
from dateutil import relativedelta as rdelta
from odoo.fields import Date, Datetime

class reporte_entrega_valores_wizard(models.TransientModel):
    _name = 'quemen.reporte_entrega_valores.wizard'
    _description = " "

    def _get_current_date(self):
        return datetime.datetime.now() - timedelta(hours=6)
    
    def _tienda_actual(self):
        tienda = False
        logging.warning('usuario ')
        logging.warning(self.env.user)
        almacen_id = self.env.user.property_warehouse_id.id
        tienda_id = self.env['pos.config'].search([('warehouse_id','=',almacen_id)])
        if len(tienda_id) > 0:
            tienda = tienda_id 
        return tienda
    
    fecha_inicio = fields.Datetime('Fecha inicio')
    fecha_fin = fields.Datetime('Fecha fin')
    tienda_id = fields.Many2one('pos.config','Tienda/Sucursal',default=_tienda_actual, required=True)
    fecha_generacion = fields.Datetime('Fecha/Hora',default=lambda self: self._get_current_date())

    def print_report(self):
        data = {
             'ids': [],
             'model': 'quemen.reporte_entrega_valores.wizard',
             'form': self.read()[0]
        }
        return self.env.ref('quemen.action_reporte_entrega_valores').report_action(self, data=data)
