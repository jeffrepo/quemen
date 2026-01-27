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

class ReportExistencias(models.AbstractModel):
    _name = 'report.quemen.reporte_existencias'
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


        return inventario

    def productos_existencia(self, tienda_id):
        logging.warning('TIENDA')
        logging.warning(tienda_id)
        tiendas_id = self.env['pos.config'].search([('id','=',tienda_id[0])])
        logging.warn("tienda_id")
        logging.warn(tiendas_id)

        ubicacion_id = tiendas_id.picking_type_id.default_location_src_id

        stock_id = self.env['stock.quant'].search([('location_id','=',ubicacion_id.id)], order='product_id asc')
        inventario = {}
        if stock_id:
            for linea in stock_id:
                logging.warn("linea")
                logging.warn(linea.product_id.name)
                if linea.lot_id and linea.lot_id.expiration_date:
                    if str(linea.product_id.categ_id.parent_id.id)+'/'+str(linea.product_id.categ_id.id) not in inventario:
                        inventario[str(linea.product_id.categ_id.parent_id.id)+'/'+str(linea.product_id.categ_id.id)] = {'productos': [],'categoria_padre': linea.product_id.categ_id.parent_id.name, 'categoria_hija': linea.product_id.categ_id.name }

                    inventario[str(linea.product_id.categ_id.parent_id.id)+'/'+str(linea.product_id.categ_id.id)]['productos'].append(linea)
                else:
                    if str(linea.product_id.categ_id.parent_id.id)+'/'+str(linea.product_id.categ_id.id) not in inventario:
                        inventario[str(linea.product_id.categ_id.parent_id.id)+'/'+str(linea.product_id.categ_id.id)] = {'productos': [],'categoria_padre': linea.product_id.categ_id.parent_id.name, 'categoria_hija': linea.product_id.categ_id.name }
                    inventario[str(linea.product_id.categ_id.parent_id.id)+'/'+str(linea.product_id.categ_id.id)]['productos'].append(linea)


        logging.warn('product existencias')
        logging.warn(inventario)
        return inventario


    def obtener_tienda(self, tienda_id):

        tienda = self.env['pos.config'].search([('id','=',tienda_id[0])])

        return tienda;

    def fecha_hora_actual(self):
        logging.warn(datetime.datetime.now())

        timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz or 'UTC')
        fecha_hora = datetime.datetime.now().astimezone(timezone).strftime('%d/%m/%Y %H:%M:%S')
        return fecha_hora

    @api.model
    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_ids', []))
        tienda_id = data['form']['tienda_id']
        docs = self.env['pos.session'].browse(docids)
        logging.warning('docs')
        logging.warning(docs)
        logging.warning(tienda_id)
        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data['form'],
            'docs': docs,
            'tienda_id': tienda_id,
            'productos_existencia': self.productos_existencia,
            'fecha_hora_actual': self.fecha_hora_actual,
            'obtener_tienda': self.obtener_tienda
        }
