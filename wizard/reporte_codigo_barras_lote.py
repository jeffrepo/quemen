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

class reporte_codigo_barras_wizard(models.TransientModel):
    _name = 'quemen.reporte_codigo_barras.wizard'
    _description = " "

    def _domain_product_ids(self):
        domain = []
        id = self.env.context.get('active_ids', [])
        op_lot_id = self.env['quemen.op_lote'].search([('id','=', id)])
        if op_lot_id:
            domain = [('id','in',op_lot_id.product_ids.ids)]
        return domain

    product_ids = fields.Many2many('quemen.op_lote_line',string='Productos', domain=_domain_product_ids)

    def print_report(self):
        data = {
             'ids': [],
             'model': 'quemen.reporte_codigo_barras.wizard',
             'form': self.read()[0],
        }

        product_ids = data['form']['product_ids']

        data['product_ids'] = product_ids

        report_reference = self.env.ref('quemen.action_report_codigo_barras_lote').report_action(self, data=data)
        report_reference.update({'close_on_report_download': True})
        return report_reference
