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

class reporte_formato_salidas_wizard(models.TransientModel):
    _name = 'quemen.reporte_formato_salidas.wizard'
    _description = " "

    tienda_id = fields.Many2one('pos.config', 'Tienda/Sucursal', default=lambda self: self.env.user.pos_id.id)
    fecha_desde = fields.Date('Fecha desde')
    fecha_hasta = fields.Date('Fecha hasta')

    def print_report(self):
        data = {
             'ids': [],
             'model': 'quemen.reporte_formato_salidas.wizard',
             'form': self.read()[0]
        }
        return self.env.ref('quemen.action_reporte_formato_salidas').report_action(self, data=data)
