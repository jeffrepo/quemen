# -*- coding: utf-8 -*-
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError, ValidationError
import logging
import pytz
from datetime import datetime, timedelta
from lxml import etree
import re
from dateutil.relativedelta import relativedelta

class StockPicking(models.Model):
    _inherit = "stock.picking"

    # l10n_mx_edi_customs_regime_ids = fields.Many2many(
    #     string="Customs Regimes",
    #     help="Regimes associated to the good's transfer (import or export).",
    #     comodel_name='l10n_mx_edi.customs.regime',
    #     ondelete='restrict',
    # )

    generar_nuevos_lotes = fields.Boolean("Generar nuevos lotes", related="picking_type_id.generar_nuevos_lotes")
    producto_ids = fields.One2many("quemen.stock_move_line", "picking_id", "Productos")
    dia_congelamiento = fields.Boolean("Día congelamiento")
    generar_nuevos_lotes_tiendas = fields.Boolean("Generar nuevos lotes tiendas", related="picking_type_id.generar_nuevos_lotes_tiendas")

    def write(self, vals):
        for picking in self:
            if 'partner_id' in vals:
                partner_id = self.env["res.partner"].search([("id", "=", vals["partner_id"])])
                logging.warning("partner_id")
                logging.warning(partner_id)
                if partner_id and partner_id.location_dest_id:
                    vals['location_dest_id'] = partner_id.location_dest_id.id
        res = super(StockPicking, self).write(vals)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for picking in res:
            vals_to_write = {}
            if picking.picking_type_id.picking_partner_id:
                vals_to_write['partner_id'] = picking.picking_type_id.picking_partner_id.id
            if picking.picking_type_id.tipo_transporte:
                vals_to_write['l10n_mx_edi_transport_type'] = picking.picking_type_id.tipo_transporte
            if vals_to_write:
                picking.write(vals_to_write)
        return res

    @api.depends('move_line_ids.state', 'move_line_ids.date', 'move_type')
    def _compute_scheduled_date(self):
        res = super(StockPicking, self)._compute_scheduled_date()
        for picking in self:
            new_datetime = picking.scheduled_date
            picking.scheduled_date = new_datetime + timedelta(hours=2)

    def button_validate(self):
        if self.generar_nuevos_lotes == True:
            if len(self.producto_ids) == 0:
                raise ValidationError("Debe de llenar la pestaña de productos")
            else:
                for linea in self.producto_ids:
                    StockQuant = self.env['stock.quant']
                    quant = StockQuant.search([('product_id', '=', linea.product_id.id), ('location_id', '=', self.location_id.id),("lot_id", "=", linea.lote_id.id)], limit=1)
                    existencia = 0
                    if quant:
                        existencia = quant.quantity

                    quant_id = self.env["stock.quant"].with_context(inventory_mode=True).sudo().create({
                        'location_id': self.location_id.id,
                        'product_id': linea.product_id.id,
                        'lot_id': linea.lote_id.id,
                        'inventory_quantity': existencia-linea.cantidad,
                    }).action_apply_inventory()
                    logging.warning("existencia")
                    logging.warning(existencia)
                    if existencia > 0:

                        elaboration_date = datetime.fromisoformat(fields.Date.today().isoformat() + ' 06:00:00') + (relativedelta(days=1) if self.dia_congelamiento else relativedelta(days=0))
                        expiration_date = elaboration_date + timedelta(days=linea.product_id.expiration_time)
                        removal_date = expiration_date
                        use_date = expiration_date
                        alert_date = expiration_date
                        nuevo_lote_id = self.env['stock.lot'].create({
                            'company_id': self.env.company.id,
                            'elaboration_date': elaboration_date,
                            'expiration_date': expiration_date,
                            'removal_date': removal_date,
                            'use_date': use_date,
                            'alert_date': alert_date,
                            'product_id': linea.product_id.id})

                        if nuevo_lote_id:
                            nuevo_quant_id = self.env["stock.quant"].with_context(inventory_mode=True).sudo().create({
                                'location_id': self.location_id.id,
                                'product_id': linea.product_id.id,
                                'lot_id': nuevo_lote_id.id,
                                'inventory_quantity': linea.cantidad,
                            }).action_apply_inventory()

                            lineas_transferencia_id = self.env['stock.move.line'].create({
                                'picking_id': self.id,
                                'product_id': linea.product_id.id,
                                #'product_uom_qty': linea.cantidad,
                                'product_uom_id': linea.product_id.uom_id.id,
                                'location_id': self.location_id.id,
                                'location_dest_id': self.location_dest_id.id,
                                'qty_done': linea.cantidad,
                                'lot_id': nuevo_lote_id.id
                            })
                        else:
                            raise ValidationError("Error al crear lote")

        if self.picking_type_id.bloqueo_traspaso == True:
            if self.note == "<p><br></p>":
              raise ValidationError("Favor de llenar las notas :@")

        #if self.picking_type_id.salida_traspaso==True:
        #    if len(self.partner_id) == 0:
        #        raise ValidationError("La dirección de entrega es requerida")
        #    if self.partner_id.location_dest_id == False:
        #        raise ValidationError("La Ubicacion de entrega dentro del contacto es requerida")

        if self.picking_type_id.tipo_operacion_porcion_id:
            transferencia_id = self.producto_porciones()
            logging.warning(transferencia_id)
            if  transferencia_id:
                transferencia_id.action_assign()
                transferencia_id.button_validate()
        for picking in self:
            for move in picking.move_ids:
                if not move.barcode:
                    continue
    
                lot = self.env['stock.lot'].search([
                    ('name', '=', move.barcode),
                ], limit=1)
    
                if not lot:
                    raise ValidationError(_("Código de barra inválido: %s") % move.barcode)
    
                product = lot.product_id
    
                quant = self.env['stock.quant'].search([
                    ('product_id', '=', product.id),
                    ('lot_id', '=', lot.id),
                    ('location_id', 'child_of', picking.location_id.id),
                    ('quantity', '>', 0),
                ], limit=1)
    
                if not quant:
                    raise ValidationError(_("No hay existencia disponible para el lote %s.") % lot.name)
    
                qty = move.quantity or move.product_uom_qty
    
                move.product_id = product.id
                move.product_uom = product.uom_id.id
                move.product_uom_qty = qty
    
                move.move_line_ids.unlink()
    
                qty_field = (
                    'picked_quantity'
                    if 'picked_quantity' in self.env['stock.move.line']._fields
                    else 'quantity'
                )
    
                self.env['stock.move.line'].create({
                    'picking_id': picking.id,
                    'move_id': move.id,
                    'product_id': product.id,
                    'product_uom_id': product.uom_id.id,
                    'location_id': quant.location_id.id,
                    'location_dest_id': picking.location_dest_id.id,
                    'lot_id': lot.id,
                    'quant_id': quant.id,
                    qty_field: qty,
                })
        res = super(StockPicking, self).button_validate()
        return res


    def producto_porciones(self):
        almacen_id = self.env.user.property_warehouse_id.id
        # tipo_operacion_porciones = self.env['stock.picking.type'].search([('warehouse_id','=', almacen_id)])
        # if len(tipo_operacion_porciones) > 0:
        lista_id = {}
        transferencia_id = False
        tipo_de_operacion = self.env.user.pos_id.producto_porciones.id
        lineas = self.move_line_ids_without_package
        tipo_de_operacion = self.picking_type_id.tipo_operacion_porcion_id
        ubicacion_id = self.picking_type_id.tipo_operacion_porcion_id.default_location_src_id
        ubicacion_dest_id = self.picking_type_id.tipo_operacion_porcion_id.default_location_dest_id
        for linea in lineas:
            if linea.product_id.producto_porciones:
                logging.warning('linea produco porcioes')

                product_porciones_id= self.env['product.product'].search([('product_tmpl_id','=',linea.product_id.producto_porciones.id)])
                qty_done = 0
                cantidad_entera = 0
                cantidad_porcion = 0
                if linea.product_id.id not in lista_id:
                    producto_id = linea.product_id.producto_porciones.id

                    # logging.warn("linea.product_id.producto_porciones.name")
                    # logging.warn(linea.product_id.producto_porciones.name)
                    hecho = linea.qty_done
                    product_uom_qty = linea.product_uom_qty
                    product_uom_id = linea.product_uom_id.id
                    location_id = linea.location_id.id
                    location_dest_id = linea.location_dest_id.id
                    lot_id = linea.lot_id.name
                    expiration_date = linea.lot_id.expiration_date
                    if self.generar_nuevos_lotes_tiendas:
                        expiration_date = datetime.fromisoformat(fields.Date.today().isoformat() + ' 06:00:00') + relativedelta(days= linea.product_id.dias_caducidad_rebanado)
                    removal_date = expiration_date
                    cantidad_entera = linea.qty_done
                    cantidad_porcion = linea.product_id.porciones
                    qty_done = cantidad_entera * cantidad_porcion
                    # logging.warn("linea.qty_done * linea.product_id.producto_porciones.porciones")
                    # logging.warn(qty_done)
                    lista_id[linea.product_id.id]={
                    'product_id': product_porciones_id.id,
                    'qty_done': hecho,
                    'product_uom_qty': product_uom_qty,
                    'product_uom_id': product_uom_id,
                    'location_id': location_id,
                    'location_dest_id': location_dest_id,
                    'lot_id': lot_id,
                    'expiration_date': expiration_date,
                    'removal_date': removal_date,
                    'qty_done': qty_done
                    }
        if  len(lista_id)>0:

            transferencia_id = self.env['stock.picking'].create({
            'picking_type_id': tipo_de_operacion.id,
            'location_id': ubicacion_id.id,
            'location_dest_id': ubicacion_dest_id.id, })

            for lneas in lista_id:
                # logging.warn("lista_id[lneas]['product_id']")
                # logging.warn(lista_id[lneas]['product_id'])

                lotes = self.env['stock.lot'].search([('name', '=', lista_id[lneas]['lot_id']), ('product_id', '=', lista_id[lneas]['product_id'])])
                lote2_id = False
                if len(lotes)>0:
                    # logging.warn(">0")
                    lote2_id = lotes
                    lote2_id.removal_date = lote2_id.expiration_date
                    # logging.warn(lote2_id)
                else:
                    # logging.warn("else")
                    lote2_id = self.env['stock.lot'].create({
                    'name': lista_id[lneas]['lot_id'],
                    'company_id': self.env.company.id,
                    'expiration_date': lista_id[lneas]['expiration_date'],
                    'removal_date':  lista_id[lneas]['removal_date'],
                    'product_id': lista_id[lneas]['product_id']})
                    # logging.warn(lote2_id)

                lineas_transferencia_id = self.env['stock.move.line'].create({
                'picking_id': transferencia_id.id,
                'product_id': lista_id[lneas]['product_id'],
                'qty_done': lista_id[lneas]['qty_done'],
                'product_uom_qty': lista_id[lneas]['product_uom_qty'],
                'product_uom_id': lista_id[lneas]['product_uom_id'],
                'location_id': ubicacion_id.id,
                'location_dest_id': ubicacion_dest_id.id,
                'qty_done': lista_id[lneas]['qty_done'],
                'lot_id': lote2_id.id
                })
        return transferencia_id

    def enviando_producto(self):
        lista_id = {}
        lista_objeto = {}
        lista_almacenes = []
        transferencia_id = False
        lineas = self.move_line_ids_without_package
        tipo_de_operacion = self.env.user.pos_id.producto_porciones.id
        ubicacion_id = self.env.user.pos_id.producto_porciones.default_location_src_id
        ubicacion_dest_id = self.env.user.pos_id.producto_porciones.default_location_dest_id

        tiendas_almacenes= self.env['pos.config'].search([])

        for tienda_almacen in tiendas_almacenes:
            if tienda_almacen.producto_porciones and tienda_almacen.producto_porciones.warehouse_id:
                lista_almacenes.append(tienda_almacen.producto_porciones.warehouse_id.id)


        # logging.warn("lista_almacenes")
        # logging.warn(lista_almacenes)


        if (self.picking_type_id.code == 'internal') and (self.picking_type_id.tipo_operacion_porcion_id) and (int(self.picking_type_id.warehouse_id.id) in lista_almacenes):
            # logging.warn("Estamos entrando C=")
            for linea in lineas:
                if (int(linea.product_id.producto_porciones.id) > 0):

                    warehouse_id = self.env.user.pos_id.producto_porciones.warehouse_id.id
                    sequence_code = self.env.user.pos_id.producto_porciones.sequence_code


                    product_porciones_id= self.env['product.product'].search([('product_tmpl_id','=',linea.product_id.producto_porciones.id)])
                    qty_done = 0
                    cantidad_entera = 0
                    cantidad_porcion = 0
                    if linea.product_id.id not in lista_id:
                        producto_id = linea.product_id.producto_porciones.id

                        # logging.warn("linea.product_id.producto_porciones.name")
                        # logging.warn(linea.product_id.producto_porciones.name)
                        hecho = linea.qty_done
                        product_uom_qty = linea.product_uom_qty
                        product_uom_id = linea.product_uom_id.id
                        location_id = linea.location_id.id
                        location_dest_id = linea.location_dest_id.id
                        lot_id = linea.lot_id.name
                        life_date = linea.lot_id.expiration_date
                        cantidad_entera = linea.qty_done
                        cantidad_porcion = linea.product_id.porciones
                        qty_done = cantidad_entera * cantidad_porcion
                        # logging.warn("linea.qty_done * linea.product_id.producto_porciones.porciones")
                        # logging.warn(qty_done)
                        lista_id[linea.product_id.id]={
                        'product_id': product_porciones_id.id,
                        'qty_done': hecho,
                        'product_uom_qty': product_uom_qty,
                        'product_uom_id': product_uom_id,
                        'location_id': location_id,
                        'location_dest_id': location_dest_id,
                        'lot_id': lot_id,
                        'life_date': life_date,
                        'qty_done': qty_done
                        }

        if  len(lista_id)>0:

            transferencia_id = self.env['stock.picking'].create({
            'picking_type_id': tipo_de_operacion,
            'location_id': ubicacion_id.id,
            'location_dest_id': ubicacion_dest_id.id, })

            for lneas in lista_id:
                # logging.warn("lista_id[lneas]['product_id']")
                # logging.warn(lista_id[lneas]['product_id'])

                lotes = self.env['stock.lot'].search([('name', '=', lista_id[lneas]['lot_id']), ('product_id', '=', lista_id[lneas]['product_id'])])
                lote2_id = False
                if len(lotes)>0:
                    # logging.warn(">0")
                    lote2_id = lotes
                    # logging.warn(lote2_id)
                else:
                    # logging.warn("else")
                    lote2_id = self.env['stock.lot'].create({
                    'name': lista_id[lneas]['lot_id'],
                    'company_id': self.env.company.id,
                    'life_date': lista_id[lneas]['life_date'],
                    'product_id': lista_id[lneas]['product_id']})
                    # logging.warn(lote2_id)

                lineas_transferencia_id = self.env['stock.move.line'].create({
                'picking_id': transferencia_id.id,
                'product_id': lista_id[lneas]['product_id'],
                'qty_done': lista_id[lneas]['qty_done'],
                'product_uom_qty': lista_id[lneas]['product_uom_qty'],
                'product_uom_id': lista_id[lneas]['product_uom_id'],
                'location_id': ubicacion_id.id,
                'location_dest_id': ubicacion_dest_id.id,
                'qty_done': lista_id[lneas]['qty_done'],
                'lot_id': lote2_id.id
                })

        return transferencia_id

    def verificar_productos_vencidos_hoy(self):
        stock_quant = self.env['stock.quant'].sudo().search([('quantity','>',0),('removal_date','!=',False)])
        timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz or 'UTC')
        fecha_hoy = datetime.now().astimezone(timezone).strftime('%Y-%m-%d')
        # Sumarle un dia a la fecha de HOY

        dia_actual = datetime.now().astimezone(timezone).strftime('%d')
        mes_ao_actual = datetime.now().astimezone(timezone).strftime('%Y-%m')
        dia_mañana = int(dia_actual) + 0
        if dia_mañana<10:
            dia_mañana = '0'+str(dia_mañana)
        fecha_mañana = str(mes_ao_actual)+'-'+str(dia_mañana)
        inventario = {}
        ubicacion_actual = False
        if stock_quant:
            for linea in stock_quant:
                if linea.location_id.id not in inventario:
                    inventario[linea.location_id.id] = {'productos':[],'bodega':linea.location_id}
                if linea.lot_id and linea.lot_id.expiration_date and (linea.lot_id.expiration_date.astimezone(timezone).strftime('%Y-%m-%d') == fecha_mañana or linea.lot_id.expiration_date.astimezone(timezone).strftime('%Y-%m-%d') <= fecha_mañana or linea.lot_id.expiration_date.astimezone(timezone).strftime('%Y-%m-%d') == fecha_hoy):
                    inventario[linea.location_id.id]['productos'].append(linea)

            tiendas_ids = self.env['pos.config'].search([('envio_salida_vencimiento_id','!=', False)])
            # picking_ids = self.env['stock.picking.type'].search([('tipo_operacion_caducidad_id','!=', False)])
            if tiendas_ids:
                for tienda in tiendas_ids:
                    ubicacion_actual = tienda.envio_salida_vencimiento_id.default_location_src_id
                    if tienda.envio_salida_vencimiento_id.default_location_src_id.id in inventario:
                        destino_id = tienda.envio_salida_vencimiento_id.default_location_dest_id
                        tipo_envio_id = tienda.envio_salida_vencimiento_id
                        # logging.warn(inventario[tienda.picking_type_id.default_location_src_id.id]['productos'])
                        if len(inventario[tienda.envio_salida_vencimiento_id.default_location_src_id.id]['productos']) > 0:
                            stock_quant_lista = []
                            logging.warning('salida vencimiento')
                            logging.warning(tienda.envio_salida_vencimiento_id.id)
                            envio = {
                                'picking_type_id': tienda.envio_salida_vencimiento_id.id,
                                'location_id': ubicacion_actual.id,
                                'location_dest_id': destino_id.id,
                                #'immediate_transfer': True,
                            }
                            envio_id = self.env['stock.picking'].create(envio)
                            for quant in inventario[tienda.envio_salida_vencimiento_id.default_location_src_id.id]['productos']:
                                # linea_envio = {
                                #     'product_id': quant.product_id.id,
                                #     'location_id': ubicacion_actual.id,
                                #     'product_uom_id': quant.product_id.uom_id.id,
                                #     'location_dest_id': salida.default_location_dest_id.id,
                                #     'lot_id': quant.lot_id.id,
                                #     'picking_id': envio_id.id
                                # }
                                move = {
                                    'product_id': quant.product_id.id,
                                    'name': quant.product_id.name,
                                    'product_uom': quant.product_id.uom_id.id,

                                    'location_id': ubicacion_actual.id,
                                    'product_uom_qty': quant.quantity,
                                    'location_dest_id': destino_id.id,
                                    # 'lot_id': quant.lot_id.id,
                                    'picking_id': envio_id.id
                                }
                                move_id = self.env['stock.move'].create(move)
                                move['move_id'] = move_id.id
                                move['lot_id'] = quant.lot_id.id
                                move['product_uom_qty'] = quant.quantity
                                stock_quant_lista.append(move)

                            # envio_id.action_confirm()
                            # envio_id.action_assign()
                            for quant in stock_quant_lista:
                                ml = {
                                    'product_id': quant['product_id'],
                                    'location_id': ubicacion_actual.id,
                                    'product_uom_id': quant['product_uom'],
                                    'location_dest_id': destino_id.id,
                                    'lot_id': quant['lot_id'],
                                    'move_id': quant['move_id'],
                                    'qty_done': quant['product_uom_qty'],
                                    'picking_id':envio_id.id,
                                }
                                move_line_id = self.env['stock.move.line'].create(ml)
                            envio_id.action_assign()
                            # envio_id.button_validate()
                            # envio_id.button_validate()

                            # envio_id.button_validate()

        return inventario

    def verificar_productos_vencidos(self):
        stock_quant = self.env['stock.quant'].sudo().search([('quantity','>',0),('removal_date','!=',False)])
        timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz or 'UTC')
        fecha_hoy = datetime.now().astimezone(timezone).strftime('%Y-%m-%d')
        # Sumarle un dia a la fecha de HOY

        dia_actual = datetime.now().astimezone(timezone).strftime('%d')
        mes_ao_actual = datetime.now().astimezone(timezone).strftime('%Y-%m')
        dia_mañana = int(dia_actual) + 1
        if dia_mañana<10:
            dia_mañana = '0'+str(dia_mañana)
        fecha_mañana = str(mes_ao_actual)+'-'+str(dia_mañana)
        inventario = {}
        ubicacion_actual = False
        if stock_quant:
            for linea in stock_quant:
                if linea.location_id.id not in inventario:
                    inventario[linea.location_id.id] = {'productos':[],'bodega':linea.location_id}
                if linea.lot_id and linea.lot_id.expiration_date and (linea.lot_id.expiration_date.astimezone(timezone).strftime('%Y-%m-%d') == fecha_mañana or linea.lot_id.expiration_date.astimezone(timezone).strftime('%Y-%m-%d') <= fecha_mañana or linea.lot_id.expiration_date.astimezone(timezone).strftime('%Y-%m-%d') == fecha_hoy):
                    inventario[linea.location_id.id]['productos'].append(linea)

            tiendas_ids = self.env['pos.config'].search([('envio_salida_vencimiento_id','!=', False)])
            # picking_ids = self.env['stock.picking.type'].search([('tipo_operacion_caducidad_id','!=', False)])
            if tiendas_ids:
                for tienda in tiendas_ids:
                    ubicacion_actual = tienda.envio_salida_vencimiento_id.default_location_src_id
                    if tienda.envio_salida_vencimiento_id.default_location_src_id.id in inventario:
                        destino_id = tienda.envio_salida_vencimiento_id.default_location_dest_id
                        tipo_envio_id = tienda.envio_salida_vencimiento_id
                        # logging.warn(inventario[tienda.picking_type_id.default_location_src_id.id]['productos'])
                        if len(inventario[tienda.envio_salida_vencimiento_id.default_location_src_id.id]['productos']) > 0:
                            stock_quant_lista = []
                            envio = {
                                'picking_type_id': tienda.envio_salida_vencimiento_id.id,
                                'location_id': ubicacion_actual.id,
                                'location_dest_id': destino_id.id,
                                #'immediate_transfer': True,
                            }
                            envio_id = self.env['stock.picking'].create(envio)
                            for quant in inventario[tienda.envio_salida_vencimiento_id.default_location_src_id.id]['productos']:
                                # linea_envio = {
                                #     'product_id': quant.product_id.id,
                                #     'location_id': ubicacion_actual.id,
                                #     'product_uom_id': quant.product_id.uom_id.id,
                                #     'location_dest_id': salida.default_location_dest_id.id,
                                #     'lot_id': quant.lot_id.id,
                                #     'picking_id': envio_id.id
                                # }
                                move = {
                                    'product_id': quant.product_id.id,
                                    #'name': quant.product_id.name,
                                    'product_uom': quant.product_id.uom_id.id,

                                    'location_id': ubicacion_actual.id,
                                    'product_uom_qty': quant.quantity,
                                    'location_dest_id': destino_id.id,
                                    # 'lot_id': quant.lot_id.id,
                                    'picking_id': envio_id.id
                                }
                                move_id = self.env['stock.move'].create(move)
                                move['move_id'] = move_id.id
                                move['lot_id'] = quant.lot_id.id
                                move['product_uom_qty'] = quant.quantity
                                stock_quant_lista.append(move)

                            # envio_id.action_confirm()
                            # envio_id.action_assign()
                            for quant in stock_quant_lista:
                                ml = {
                                    'product_id': quant['product_id'],
                                    'location_id': ubicacion_actual.id,
                                    'product_uom_id': quant['product_uom'],
                                    'location_dest_id': destino_id.id,
                                    'lot_id': quant['lot_id'],
                                    'move_id': quant['move_id'],
                                    'qty_done': quant['product_uom_qty'],
                                    'picking_id':envio_id.id,
                                }
                                move_line_id = self.env['stock.move.line'].create(ml)
                            envio_id.action_assign()
                            # envio_id.button_validate()
                            # envio_id.button_validate()

                            # envio_id.button_validate()

        return inventario

class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    tipo_operacion_caducidad_id = fields.Many2one('stock.picking.type', string='Tipo operacion caducidad')
    # porciones = fields.Boolean('Porciones?')
    tipo_operacion_porcion_id = fields.Many2one('stock.picking.type', string='Tipo operacion porcion')
    picking_partner_id = fields.Many2one('res.partner','Contacto')
    tipo_transporte = fields.Selection([('00', 'Sin uso de Carreteras Federales'), ('01', 'Autotransporte Federal')], string='Tipo de transporte')
    salida_traspaso = fields.Boolean("Salida por traspaso")
    generar_nuevos_lotes = fields.Boolean("Generar nuevos lotes")
    bloqueo_traspaso = fields.Boolean("Bloqueo traspasos")
    generar_nuevos_lotes_tiendas = fields.Boolean("Generar nuevos lotes tiendas")
