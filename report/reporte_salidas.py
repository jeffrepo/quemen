
# -*- encoding: utf-8 -*-

from odoo import api, models, fields
from datetime import date
import datetime
import time
import dateutil.parser
from dateutil.relativedelta import relativedelta
from dateutil import relativedelta as rdelta
from odoo.fields import Date, Datetime
import logging
from operator import itemgetter
import pytz

class ReportSalidas(models.AbstractModel):
    _name = 'report.quemen.reporte_salidas'
    _description = " "

    def _get_tienda(self,tienda):
        tienda_id = self.env['pos.config'].search([('id','=',tienda[0])])
        return tienda_id

    def _get_tipo_operacion(self,tipo_operacion):
        tipo_operacion_id = self.env['stock.picking.type'].search([('id','=',tipo_operacion[0])])
        return tipo_operacion_id

    def salida_productos(self,fecha_desde,fecha_hasta,tipo_operacion):
        tipo_operacion_id = self.env['stock.picking.type'].search([('id','=',tipo_operacion[0])])
        salidas = self.env['stock.picking'].search([('picking_type_id','=', tipo_operacion_id.id),('state','=','done'),('date_done','>=',fecha_desde),('date_done','<=',fecha_hasta)])
        movimientos = []
        if salidas:
            for salida in salidas:
                for linea in salida.move_line_ids_without_package:
                    dic ={
                        'nombre': linea.product_id.name,
                        'codigo_barra': linea.product_id.barcode,
                        'cantidad': linea.qty_done,
                        'fecha_caducidad': linea.lot_id.life_date.strftime('%d/%m/%Y'),
                        'destino': str(salida.user_id.name) +' ' +str(salida.picking_type_id.default_location_dest_id.name)
                    }
                    movimientos.append(dic)

        # envios = self.env['stock.picking'].search([('location_id','=',self.env.user.pos_id.picking_type_id.default_location_src_id.id),('scheduled_date','>=',fecha_desde),('scheduled_date','<=',fecha_hasta)])
        # productos = []
        # if envios:
        #     logging.warn(envios)
        #     for envio in envios:
        #         if envio.picking_type_id.devolucion_productos_vencidos:
        #             for linea in envio.move_line_ids_without_package:
        #
        #                 productos.append({'linea': linea, 'fecha_vencimiento': linea.lot_id.life_date.strftime('%Y-%m-%d')})
        return movimientos



    @api.model
    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_ids', []))
        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data['form'],
            'docs': docs,
            'salida_productos': self.salida_productos,
            '_get_tienda': self._get_tienda,
            '_get_tipo_operacion': self._get_tipo_operacion,
        }
