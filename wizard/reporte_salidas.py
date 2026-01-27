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

class reporte_salidas_wizard(models.TransientModel):
    _name = 'quemen.reporte_salidas.wizard'
    _description = " "

    fecha_desde = fields.Date('Fecha desde')
    fecha_hasta = fields.Date('Fecha hasta')
    tipo_operacion_id = fields.Many2one('stock.picking.type','Tipo de operacion')
    tienda_id = fields.Many2one('pos.config','Tienda')

    def print_report(self):
        data = {
             'ids': [],
             'model': 'quemen.reporte_salidas.wizard',
             'form': self.read()[0]
        }
        return self.env.ref('quemen.action_reporte_salidas').report_action(self, data=data)
