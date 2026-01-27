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

class quemen_reporte_retiros_sesion(models.TransientModel):
    _name = 'quemen.reporte_retiros_sesion.wizard'
    _description = " "

    def ultimo_retiro(self):
        sesiones = self.env['pos.session'].search([('config_id', '=' ,self.env.user.pos_id.id)])
        lista_sesion = []
        mayor = 0
        opened = 'opened'
        fecha = 0
        for usuario in sesiones:
            lista_sesion.append(usuario)

        posicion = 0
        fecha_primera_posicion = None
        for lst_id in lista_sesion:
            for id_retiro in lst_id.retiros_ids:
                if lst_id.state == opened:
                    if fecha_primera_posicion == None:
                        fecha_primera_posicion = lst_id.retiros_ids[0].fecha_hora
                    else:
                        fecha_reciente = id_retiro.fecha_hora
                        if fecha_reciente > fecha_primera_posicion:
                            fecha_primera_posicion = fecha_reciente
                mayor = fecha_primera_posicion


                if mayor == id_retiro.fecha_hora:
                    ultimo = id_retiro.id

        return ultimo

    retiro_id = fields.Many2one('quemen.retiros','Retiro', default=ultimo_retiro)

    def print_report(self):
        data = {
             'ids': [],
             'model': 'quemen.reporte_retiros_sesion.wizard',
             'form': self.read()[0]
        }
        return self.env.ref('quemen.action_reporte_retiros').report_action(self, data=data)
