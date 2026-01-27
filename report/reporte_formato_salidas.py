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
# import odoo.addons.hr_gt.a_letras

class ReportFormatoSalidas(models.AbstractModel):
    _name = 'report.quemen.reporte_formato_salidas'
    _description = " "

    def verificar_productos_vencidos(self):
        logging.warn('verificar para albaran')
        stock_quant = self.env['stock.quant'].search([('quantity','>',0)])
        timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz or 'UTC')
        fecha_hoy = datetime.datetime.now().astimezone(timezone).strftime('%Y-%m-%d')
        logging.warn(fecha_hoy)
        inventario = {}
        if stock_quant:
            for linea in stock_quant:
                if linea.location_id.id not in inventario:
                    inventario[linea.location_id.id] = {'productos':[],'ubicacion':linea.location_id}

                if linea.lot_id and linea.lot_id.life_date and linea.lot_id.life_date.strftime('%Y-%m-%d') == fecha_hoy:
                    logging.warn(linea.lot_id.life_date)
                    inventario[linea.location_id.id]['productos'].append(linea)

        logging.warn(inventario)
        logging.warn('termina')
        inventario = inventario.values()
        for dato in inventario:
            logging.warn(dato)
            if len(dato['productos']) > 0:
                ubicacion = dato['ubicacion']
                tipo_albaran = self.env['stock.picking.type'].search([('default_location_src_id','=', ubicacion.id),('devolucion_productos_vencidos','=',True)])
                if tipo_albaran:
                    logging.warn('tipo albaran')
                    logging.warn(tipo_albaran)
                    moves = {}
                    envio = {'picking_type_id': tipo_albaran.id,'location_id': tipo_albaran.default_location_src_id.id, 'location_dest_id': tipo_albaran.default_location_dest_id.id}
                    picking_id = self.env['stock.picking'].create(envio)
                    for linea in dato['productos']:
                        mv = {'name': linea.product_id.name,'product_id': linea.product_id.id,
                        'product_uom':linea.product_uom_id.id,
                        'product_uom_qty': linea.quantity,'picking_id':picking_id.id,'location_id':tipo_albaran.default_location_src_id.id,'location_dest_id':tipo_albaran.default_location_dest_id.id}
                        move_id = self.env['stock.move'].create(mv)
                        # move_id.write({'move_line_ids':[(0, 0, {'move_id':move_id.id,'location_id': move_id.location_id.id, 'location_dest_id': move_id.location_dest_id.id,'lot_id':linea.lot_id.id,'qty_done': linea.quantity,'product_uom_id': linea.product_uom_id.id,'company_id':tipo_albaran.company_id.id})]})
                        if move_id.id not in moves:
                            moves[move_id.id] = {'move': move_id,'lot_id': linea.lot_id}
                    picking_id.action_assign()

                    # for linea in picking_id.

                    # for m in moves.values():
                    #     ml = {'move_id': m['move'].id,'location_id': m['move'].location_id.id, 'location_dest_id': m['move'].location_dest_id.id,'lot_id':m['lot_id'].id,'qty_done': m['move'].product_uom_qty,'product_uom_id': m['move'].product_uom.id,'company_id':tipo_albaran.company_id.id}
                    #     move_line = self.env['stock.move.line'].create(ml)
                        # if move_id:
                        #     ml = {'move_id':move_id.id,'location_id': move_id.location_id.id, 'location_dest_id': move_id.location_dest_id.id,'lot_id':linea.lot_id.id,'qty_done': linea.quantity,'product_uom_id': linea.product_uom_id.id,'company_id':tipo_albaran.company_id.id}
                        #     move_line = self.env['stock.move.line'].create(ml)

        return inventario

    def productos_existencia(self, tienda_id):
        # logging.warn(fecha_vencimiento)
        # self.verificar_productos_vencidos()
        tienda_id = self.env['pos.config'].search([('id','=',tienda_id[0])])


        ubicacion_id = tienda_id.picking_type_id.default_location_src_id
        stock_id = self.env['stock.quant'].search([('location_id','=',ubicacion_id.id)])
        logging.warn("Stock_id")
        logging.warn(stock_id)
        inventario = {}
        if stock_id:
            for linea in stock_id:
                if linea.lot_id and linea.lot_id.life_date:
                    if str(linea.product_id.categ_id.parent_id.id)+'/'+str(linea.product_id.categ_id.id) not in inventario:
                        inventario[str(linea.product_id.categ_id.parent_id.id)+'/'+str(linea.product_id.categ_id.id)] = {'productos': [],'categoria_padre': linea.product_id.categ_id.parent_id.name, 'categoria_hija': linea.product_id.categ_id.name }

                    inventario[str(linea.product_id.categ_id.parent_id.id)+'/'+str(linea.product_id.categ_id.id)]['productos'].append(linea)


        logging.warn('product existencias')
        logging.warn(inventario)
        return inventario


    def salida_productos_vencidos(self,fecha_desde,fecha_hasta):
        envios = self.env['stock.picking'].search([('location_id','=',self.env.user.pos_id.picking_type_id.default_location_src_id.id),('scheduled_date','>=',fecha_desde),('scheduled_date','<=',fecha_hasta)])
        productos = []
        if envios:
            for envio in envios:
                logging.warn("Envio")
                logging.warn(envio)
                if envio.picking_type_id.devolucion_productos_vencidos:
                    for linea in envio.move_line_ids_without_package:

                        productos.append({'linea': linea, 'fecha_vencimiento': linea.lot_id.life_date.strftime('%Y-%m-%d')})

        return productos

    def fecha_hora_actual(self):
        logging.warn(datetime.datetime.now())

        timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz or 'UTC')
        fecha_hora = datetime.datetime.now().astimezone(timezone).strftime('%d/%m/%Y %H:%M:%S')
        return fecha_hora

    def obtener_tienda(self, tienda_id):

        tienda = self.env['pos.config'].search([('id','=',tienda_id[0])])

        return tienda

    # def pagos_deducciones(self,o):
    #     ingresos = 0
    #     descuentos = 0
    #     datos = {'ordinario': 0, 'extra_ordinario':0,'bonificacion':0}
    #     for linea in o.linea_ids:
    #         if linea.salary_rule_id.id in o.company_id.ordinario_ids.ids:
    #             datos['ordinario'] += linea.total
    #         elif linea.salary_rule_id.id in o.company_id.extra_ordinario_ids.ids:
    #             datos['extra_ordinario'] += linea.total
    #         elif linea.salary_rule_id.id in o.company_id.bonificacion_ids.ids:
    #             datos['bonificacion'] += linea.total
    #     return True

    # @api.model
    # def _get_report_values(self, docids, data=None):
    #     return self.get_report_values(docids, data)


# {'context': {'tz': False, 'uid': 1, 'params':
# {'action': 473}, 'active_model': 'hr_gt.recibo_pago.wizard', 'active_id': 5, 'active_ids': [5], 'search_disable_custom_filters': True}, 'ids': [], 'model': 'hr_gt.recibo_pago.wizard', 'form': {'id': 5, 'nomina_ids': [17], 'formato_recibo_pago_id': [1, 'RECIBO DE PAGO PLANILLA'], 'fecha_inicio': False, 'fecha_fin': False, 'create_uid': [1, 'Administrator'], 'create_date': '2020-06-22 01:42:19', 'write_uid': [1, 'Administrator'], 'write_date': '2020-06-22 01:42:19', 'display_name': 'hr_gt.recibo_pago.wizard,5', '__last_update': '2020-06-22 01:42:19'}}

    @api.model
    def _get_report_values(self, docids, data=None):
        # model = self.env.context.get('active_model')
        # docs = self.env[model].browse(self.env.context.get('active_ids', []))
        # tienda_id = data['form']['tienda_id']
        docs = self.env['purchase.order'].browse(docids)

        return {
            'doc_ids': self.ids,
            # 'doc_model': model,
            # 'data': data['form'],
            'docs': docs,
            # 'productos_existencia': self.productos_existencia,
            # 'fecha_hora_actual': self.fecha_hora_actual,
            'obtener_tienda': self.obtener_tienda,
            'salida_productos_vencidos': self.salida_productos_vencidos,
            # 'mes_letras': self.mes_letras,
            # 'fecha_hoy': self.fecha_hoy,
            # 'a_letras': odoo.addons.hr_gt.a_letras,
            # 'datos_recibo': self.datos_recibo,
            # 'lineas': self.lineas,
            # 'horas_extras': self.horas_extras,
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
