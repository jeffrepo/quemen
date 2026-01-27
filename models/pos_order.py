# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

class PosOrder(models.Model):
    _inherit = 'pos.order'

    tipo_venta = fields.Selection([ ('mesas', 'Mesas'),('mostrador', 'Mostrador'),('domicilio', 'A domicilio'),('especial', 'Pedidos especiales')],'Tipo de venta')
    pedido_especial = fields.Boolean('Pedido especial')
    fecha_especial = fields.Date(string="Fecha entrega")
    hora_especial = fields.Char(string="Hora entrega")
    observaciones_especial = fields.Char("Observaciones")
    sucursal_entrega = fields.Char("Sucursal de entrega")
    autorizo_especial = fields.Char("Autorizó")
    invalido = fields.Boolean('Invalido')

    def buscar_inventario(self, products_order, ubicacion_id):
        lote_no_existente = []
        productos_sin_existencia = []
        productos_agrupados = {}
        for po in products_order:
            llave = str(po['producto'])
            if po['lote']:
                llave = str(po['producto']) + '-' + str(po['lote'])
            if llave not in productos_agrupados:
                productos_agrupados[llave] = {'lot_id': po['lote'] , 'producto': po['producto'], 'qty': 0}
            productos_agrupados[llave]['qty'] += po['qty']

        for pa in productos_agrupados:
            producto = productos_agrupados[pa]['producto']

            lote = productos_agrupados[pa]['lot_id']
            stock_quant = self.env['stock.quant'].search([('location_id','=',ubicacion_id) ,('product_id','=', producto)])
            cantidad = productos_agrupados[pa]['qty']
            if lote:
                stock_quant = self.env['stock.quant'].search([('lot_id.name','=',lote), ('location_id','=',ubicacion_id) ,('product_id','=', producto)])
            
            if len(stock_quant) == 0:
                lote_no_existente.append(lote)
            else:
                if stock_quant.quantity < cantidad:
                    productos_sin_existencia.append(stock_quant.product_id.name)
                    
        return lote_no_existente, productos_sin_existencia

    @api.model
    def _order_fields(self, ui_order):
        res = super(PosOrder, self)._order_fields(ui_order)
        session = self.env['pos.session'].search([('id', '=', res['session_id'])], limit=1)

        if 'fecha' in ui_order:
            mal_formato = ui_order['fecha']

            res['hora_especial'] = ui_order['hora']
            res['fecha_especial'] = ui_order['fecha']
            res['observaciones_especial']= ui_order['observaciones']
            res['sucursal_entrega'] = ui_order['sucursal_entrega']
            res['autorizo_especial']=ui_order['autorizo']

        return res

    def _prepare_invoice_vals(self):
        res = super(PosOrder, self)._prepare_invoice_vals()
        l10n_mx_edi_payment_method_id = False
        if self.payment_ids:
            for line in self.payment_ids:
                if line.amount > 0:
                    variable = False
                    if line.payment_method_id.name == "Efectivo":
                        variable = '01'
                    elif line.payment_method_id.name in ["Tarjeta credito","Tarjeta credito Netpay"]:
                        variable = '04'
                    elif line.payment_method_id.name in ["Tarjeta debito","Tarjeta debito Netpay"]:
                        variable = '28'
                    elif line.payment_method_id.name == 'Transferencia':
                        variable = '03'
                    else:
                        variable = '01'
                    l10n_mx_edi_payment_method_id = self.env['l10n_mx_edi.payment.method'].search([('code','=',variable)])
        res['l10n_mx_edi_payment_method_id'] = l10n_mx_edi_payment_method_id
        return res

    def _prepare_invoice_line(self, order_line):
        res = super(PosOrder, self)._prepare_invoice_line(order_line)
        if res:
            res['pedido_referencia'] = order_line.order_id.name
            res['sesion_id'] = order_line.order_id.session_id.id
            res['pedido_id'] = order_line.order_id.id
        return res

class PosMakePayment(models.TransientModel):
    _inherit = 'pos.make.payment'

    def check(self):
        order = self.env['pos.order'].browse(self.env.context.get('active_id', False))
        if order.note == False and order.amount_total < 0:
            raise ValidationError("No está permitido validar la devolución hasta que ingrese el motivo de la devolución en la pestaña de notas")
        else:
            res = super(PosMakePayment, self).check()
            return res
