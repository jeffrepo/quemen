# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import time
import base64
import xlsxwriter
import io
import logging
from datetime import date
import datetime
import dateutil.parser
from dateutil.relativedelta import relativedelta
from dateutil import relativedelta as rdelta
from odoo.fields import Date, Datetime

class reporte_productos_labor_venta_wizard(models.TransientModel):
    _name = 'quemen.reporte_productos_labor_venta.wizard'
    _description = " "

    def _tienda_actual(self):
        tienda = False
        logging.warning('usuario ')
        logging.warning(self.env.user)
        almacen_id = self.env.user.property_warehouse_id.id
        tienda_id = self.env['pos.config'].search([('warehouse_id','=',almacen_id)])
        if len(tienda_id) > 0:
            tienda = tienda_id 
        return tienda
    
    tienda_id = fields.Many2one('pos.config', 'Tienda/Sucursal', default=_tienda_actual)

    def print_report(self):
        data = {
             'ids': [],
             'model': 'quemen.reporte_productos_labor_venta.wizard',
             'form': self.read()[0]
        }
        return self.env.ref('quemen.action_reporte_productos_labor_venta').report_action(self, data=data)
