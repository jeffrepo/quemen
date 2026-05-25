# -*- coding: utf-8 -*-
from odoo import api, fields, models, SUPERUSER_ID, _
from datetime import date
from datetime import datetime, timedelta
from odoo.exceptions import UserError, ValidationError
import logging
import pytz
from odoo.tools import float_compare

class QuemenStockMoveLine(models.Model):
    _name = "quemen.stock_move_line"
    _description = " . "

    picking_id = fields.Many2one("stock.picking", "Picking")
    product_id = fields.Many2one("product.product", "Producto")
    lote_id = fields.Many2one("stock.lot", "Lote")
    cantidad = fields.Float("Cantidad")
    qty_label = fields.Float("Cantidad etiqueta")

class QuemenPromociones(models.Model):
    _name = "quemen.promociones"
    _description = " . "

    name = fields.Char("Nombre")
    fecha_inicio = fields.Datetime("Fecha inicio")
    fecha_fin = fields.Datetime("Fecha fin")
    combos_ids = fields.One2many('quemen.promociones_combos','promocion_id',string="Combos")
    dosporuno_ids = fields.One2many('quemen.promociones_dosporuno','promocion_id',string="2X1")

class QuemenPromocionesCombos(models.Model):
    _name = "quemen.promociones_combos"
    _description = " . "

    promocion_id = fields.Many2one('quemen.promociones','Promocion')
    producto_id = fields.Many2one('product.product','Producto')
    cantidad = fields.Integer('Cantidad compra')
    porcentaje_descuento = fields.Float('% Descuento')
    productos_promocion_ids = fields.Many2many('product.product','quemen_productosp_rel',string="Productos promocion")

class QuemenPromocionesDosporUno(models.Model):
    _name = "quemen.promociones_dosporuno"
    _description = " . "

    promocion_id = fields.Many2one('quemen.promociones','Promocion')
    producto_id = fields.Many2one('product.product','Producto')
    productos_promocion_ids = fields.Many2many('product.product','quemen_dosporuno_rel',string="Productos promocion")


class QuemenRelojChecador(models.Model):
    _name = "quemen.reloj_checador"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Reloj checador"

    ac = fields.Char('AC.No')
    empleado_id = fields.Many2one('hr.employee','Empleado')
    departamento_id = fields.Many2one('hr.department','Departamento')
    area_id = fields.Many2one('stock.lot','Area')
    puesto_id = fields.Many2one('hr.job','Puesto')
    dia = fields.Selection([
        ('lunes', 'Lunes'),
        ('martes', 'Martes'),
        ('miercoles', 'Miercoles'),
        ('jueves', 'Jueves'),
        ('viernes', 'Viernes'),
        ('sabado', 'Sabado'),
        ('domingo', 'Domingo')],'Día')
    fecha = fields.Date('Fecha')
    hora_entrada = fields.Float('Hora de entrada')
    hora_salida = fields.Float('Hora de salida')
    horas_laboradas = fields.Float('Horas laboradas')
    jornada_laborada = fields.Float('Jornada laborada')
    horas_extras_laboradas = fields.Float('Horas extras laboradas')

class QuemenRetirosEfectivo(models.Model):
    _name = "quemen.retiros_efectivo"
    _description = "Retiros de POS"

    def _denominacion_actual(self):
        denominacion_ids = self.env['pos.bill'].search([('id','>', 0)], order='value asc')
        lista_denominaciones = []
        if len(denominacion_ids) > 0:
            for denominacion in denominacion_ids:
                if denominacion.value >= 0.50:
                    valor = {'denominacion_id': denominacion.id, 'cantidad': 0.00}
                    lista_denominaciones.append((0,0,valor))
        return lista_denominaciones


    def _sesion_actual(self):
        sesion = False
        sesion_id = self.env['pos.session'].search([('user_id','=',self.env.user.id),('state','in',['opened','closing_control'])])
        if len(sesion_id) > 0:
            sesion = sesion_id
        # else:
        #     raise ValidationError(_('No puede retirar efectivo'))
        return sesion

    @api.depends('denominacion_ids')
    def _calcular_total(self):
        for retiro in self:
            total = 0
            for linea in retiro.denominacion_ids:
                total += (linea.cantidad * linea.denominacion_id.value)
            retiro.total = total

    name = fields.Char('Nombre', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    usuario_id = fields.Many2one('res.users','usuario',default=lambda self: self.env.user)
    fecha_hora = fields.Datetime('Hora',default=fields.Datetime.now)
    sesion_id = fields.Many2one('pos.session','Sesión', default=_sesion_actual, required=True, store=True)
    tienda_id = fields.Many2one('pos.config','tienda', related='sesion_id.config_id', store=True)
    motivo = fields.Char('Motivo', required=True, default = "Retiro de efectivo")
    total = fields.Float('Total', compute='_calcular_total')
    denominacion_ids = fields.One2many('quemen.retiro_denominacion','retiro_id',string="Denominaciones",default=_denominacion_actual)
    state = fields.Selection(
    [('borrador', 'Borrador'), ('confirmado', 'Confirmado')],
    'Estado', readonly=True, copy=False, default= "borrador")
    cajero = fields.Char('Cajero', required=True, default=lambda self: self.env.user.name)
    entregado = fields.Boolean('Entregado', readonly=True)
    ultimo_retiro = fields.Boolean("último retiro")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            secuencia_id = self.env['pos.session'].search([('id', '=', vals['sesion_id'])]).config_id.secuencia_id
            if vals.get('name', _('New')) == _('New'):
                seq_date = None
                if 'company_id' in vals:
                    vals['name'] = self.env['ir.sequence'].next_by_code('quemen.op_lote', sequence_date=seq_date) or _('New')
                else:
                    vals['name'] = secuencia_id._next() or _('New')
        result = super(QuemenRetirosEfectivo, self).create(vals_list)
        return result

    def confirmar_retiro(self):
        for retiro in self:
            if retiro.state != "confirmado":
                if retiro.total > retiro.tienda_id.efectivo_maximo:
                    raise ValidationError(_('El total del retiro no puede ser mayor que el limite de efectivo configurado'))
                retiro.sesion_id.cash_register_id.write({'line_ids': [(0, 0,  { 'payment_ref': retiro.motivo, 'amount': retiro.total*-1})] })
                retiro.write({'state': 'confirmado'})


class QuemenRetiros(models.Model):
    _name = "quemen.retiro_denominacion"
    _description = " . "

    retiro_id = fields.Many2one('quemen.retiros_efectivo','Retiro')
    denominacion_id = fields.Many2one('pos.bill','Denominacion')
    cantidad = fields.Integer('Cantidad')

class QuemenRetiros(models.Model):
    _name = "quemen.retiros"
    _description = "Retiros de POS"

    name = fields.Char('Nombre', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    session_id = fields.Many2one('pos.session','Sesión')
    # cash_box_id = fields.Many2one('account.bank.statement.cashbox','Caja de efectivo')
    # usuario_id = fields.Many2one('res.users','usuario',default=lambda self: self.env.user)
    # fecha_hora = fields.Datetime('Hora',default=fields.Datetime.now)
    # motivo = fields.Char('Motivo')
    # total = fields.Float('Total')

    # @api.model
    # def create(self, vals):
    #     if vals.get('name', _('New')) == _('New'):
    #         seq_date = None
    #         if 'company_id' in vals:
    #             vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code(
    #                 'quemen.retiros', sequence_date=seq_date) or _('New')
    #         else:
    #             vals['name'] = self.env['ir.sequence'].next_by_code('quemen.retiros', sequence_date=seq_date) or _('New')

    #     result = super(QuemenRetiros, self).create(vals)
    #     return result

class QuemenOpLote(models.Model):
    _name = "quemen.op_lote"
    _description = " . "
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Nombre', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'), tracking=True)
    date = fields.Date('Fecha', tracking=True)
    date_mrp_production = fields.Date('Fecha producción', tracking=True)
    product_ids = fields.One2many('quemen.op_lote_line', 'lot_id', string="Productos", tracking=True)
    reference = fields.Char('Referencia', tracking=True)
    state = fields.Selection(
        [('borrador', 'Borrador'), ('confirmado', 'Confirmado'), ('despachado', 'Despachado')],
        'Estado', readonly=True, copy=False, default='borrador', tracking=True)
    despacho_id = fields.Many2one('stock.picking','Despacho')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                seq_date = None
                if 'company_id' in vals:
                    vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code(
                        'quemen.retiros', sequence_date=seq_date) or _('New')
                else:
                    vals['name'] = self.env['ir.sequence'].next_by_code('quemen.op_lote', sequence_date=seq_date) or _('New')

        result = super(QuemenOpLote, self).create(vals_list)
        return result

    def create_lot(self):
        for lot in self:
            if lot.product_ids and lot.state == "borrador":
                for line in lot.product_ids:
                    if len(line.lot_barcode_id) == 0:
                        elaboration_date = datetime.fromisoformat(line.elaboration_date.isoformat() + ' 06:00:00')
                        expiration_date = elaboration_date + timedelta(days=line.product_id.expiration_time)
                        removal_date = elaboration_date + timedelta(days=line.product_id.removal_time)
                        use_date = elaboration_date + timedelta(days=line.product_id.use_time)
                        alert_date = elaboration_date + timedelta(days=line.product_id.alert_time)
                        lot_id = self.env['stock.lot'].create({'product_id': line.product_id.id,
                                                                          'elaboration_date': elaboration_date,
                                                                          'expiration_date': expiration_date,
                                                                          'removal_date': removal_date,
                                                                          'use_date': use_date,
                                                                          'alert_date': alert_date,
                                                                          'company_id': 1})

                        if lot_id:
                            line.write({'lot_barcode_id': lot_id})
    def confirm_out(self):
        for lot in self:
            error_msg = ''
            if lot.product_ids:

                tipo_operacion_id = self.env['stock.picking.type'].search([("name","=","Transitoria fabricacion")])
                ubicacion_origen_id =  tipo_operacion_id.default_location_src_id.id
                ubicacion_destino_id = tipo_operacion_id.default_location_dest_id.id
                envio = {
                    'picking_type_id': tipo_operacion_id.id,
                    'location_id': ubicacion_origen_id,
                    'location_dest_id': ubicacion_destino_id,
                    'move_type': 'direct',
                }
                envio_id = self.env['stock.picking'].create(envio)
                info = self.env['report.quemen.reporte_explosion_insumos'].get_info(lot)[1]['mp']
                for product in info:
                    logging.warning("----PRODUCT")
                    logging.warning(product)
                    product_id = info[product]["product"]
                    quantity = info[product]["quantity_exp"]
                    move = {
                        'product_id': product_id.id,
                        #'name': mrp_line.product_id.name,
                        'product_uom':product_id.uom_id.id,
                        'location_id': ubicacion_origen_id,
                        'product_uom_qty': quantity,
                        'location_dest_id': ubicacion_destino_id,
                        # 'lot_id': quant.lot_id.id,
                        'picking_id': envio_id.id
                    }
                    move_id = self.env['stock.move'].create(move)
                    move['move_id'] = move_id.id
                    
                logging.warning("envio")
                logging.warning(envio)
                logging.warning(tipo_operacion_id)
                
                
                #for line in lot.product_ids:
                #    qty_bom = line.product_id.bom_ids[0].product_qty
                #    if line.product_id.bom_ids and line.product_id.bom_ids.bom_line_ids:
                #        for mrp_line in line.product_id.bom_ids[0].bom_line_ids:
                            
                #            move = {
                #                'product_id': mrp_line.product_id.id,
                #                #'name': mrp_line.product_id.name,
                #               'product_uom': mrp_line.product_id.uom_id.id,
                #                'location_id': ubicacion_origen_id,
                 #               'product_uom_qty': mrp_line.product_qty * qty_bom,
                  #              'location_dest_id': ubicacion_destino_id,
                                # 'lot_id': quant.lot_id.id,
                   #             'picking_id': envio_id.id
                   #         }
                    #        move_id = self.env['stock.move'].create(move)
                     #       move['move_id'] = move_id.id
                lot.despacho_id = envio_id.id
            lot.write({'state': "despachado"})
            

    def confirm_lot(self):
        for lot in self:
            error_msg = ''
            if lot.product_ids:
                for line in lot.product_ids:
                    if line.lot_barcode_id == False:
                        raise ValidationError(_('No puede validar productos sin Lote.'))
                    date_planed_start = datetime.fromisoformat(lot.date_mrp_production.isoformat() + ' 06:00:00')
                    qyt_bom = 1
                    if line.product_id.bom_ids:
                        qty_bom = line.product_id.bom_ids[0].product_qty
                    
                    mrp_order = {
                        # 'name': line.lot_id.name,
                        'product_id': line.product_id.id,
                        'product_uom_id': line.product_id.uom_id.id,
                        'qty_producing': line.quantity * qty_bom,
                        'product_qty': line.quantity * qty_bom,
                        'bom_id': line.product_id.bom_ids.id,
                        'origin': line.lot_id.name,
                        'lot_producing_ids': [line.lot_barcode_id.id],
                        'date_start': date_planed_start,
                        'picking_type_id': line.product_id.bom_ids.picking_type_id.id,
                        'location_src_id': line.product_id.bom_ids.picking_type_id.default_location_src_id.id,
                        'location_dest_id': line.product_id.bom_ids.picking_type_id.default_location_dest_id.id
                        # 'move_line_id': line.id,
                    }
                    mrp_order_id = self.env['mrp.production'].create(mrp_order)

                    mrp_order_id._compute_move_raw_ids()
                    mrp_order_id._compute_move_finished_ids()

                    if mrp_order_id.product_tracking == 'serial' and float_compare(mrp_order_id.qty_producing, 1, precision_rounding=mrp_order_id.product_uom_id.rounding) == 1:
                        mrp_order_id.qty_producing = 1
                    else:
                        mrp_order_id.qty_producing = mrp_order_id.product_qty - mrp_order_id.qty_produced
                    mrp_order_id._set_qty_producing()
                    for move in mrp_order_id.move_raw_ids.filtered(lambda m: m.state not in ['done', 'cancel']):
                        rounding = move.product_uom.rounding
                        for move_line in move.move_line_ids:
                            if move_line.quantity:
                                move_line.qty_done = min(move_line.quantity, move_line.move_id.should_consume_qty)
                            if float_compare(move.quantity, move.should_consume_qty, precision_rounding=rounding) >= 0:
                                break
                        if float_compare(move.quantity, move.quantity, precision_rounding=move.product_uom.rounding) == 1:
                            if move.has_tracking in ('serial', 'lot'):
                                error_msg += "\n  - %s" % move.product_id.display_name
            lot.write({'state': "confirmado"})
        return True

class QuemenOpLoteLinea(models.Model):
    _name = "quemen.op_lote_line"
    _description = " . "
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = "product_id"

    lot_id = fields.Many2one("quemen.op_lote", "Lote")
    product_id = fields.Many2one('product.product', 'Producto', tracking=True)
    quantity = fields.Float('Cantidad', tracking=True)
    elaboration_date = fields.Date('Fecha elaboracion', tracking=True)
    qty_label = fields.Float('Cantidad etiquetas', default=1)
    lot_barcode_id = fields.Many2one('stock.lot', 'Lote código de barras', tracking=True)

    # FIX: related -> no selection. Hereda el selection del campo origen (lot_id.state)
    lot_state = fields.Selection(related='lot_id.state', string='Estado', store=True, readonly=True)

    @api.onchange('quantity')
    def _onchange_quantity(self):
        if self.product_id:
            self.qty_label = self.quantity

class QuemenPlanning(models.Model):
    _name = "quemen.planning"
    _description = " . "
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Nombre', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'), tracking=True)
    date = fields.Date('Fecha', tracking=True)
    planning_date = fields.Date('Fecha planificada', tracking=True)
    product_ids = fields.One2many('quemen.planning_line', 'planning_id', string="Productos", tracking=True)
    reference = fields.Char('Referencia', tracking=True)
    state = fields.Selection('Estado', readonly=True, copy=False, default='borrador', tracking=True)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            seq_date = None
            vals['name'] = self.env['ir.sequence'].next_by_code('quemen.planning', sequence_date=seq_date) or _('New')

        result = super(QuemenPlanning, self).create(vals)
        return result

    def show_components(self):
        list_components = []
        for p in self:
            if p.product_ids:
                for line in p.product_ids:
                    origin_lines_dic = {
                        'product_id': line.product_id,
                        'qty': line.qty,
                        'line': line,
                    }
                    line.unlink()
                    list_components.append(origin_lines_dic)

        if len(list_components) > 0:
            for lc in list_components:
                group_product_components = []
                product_id = lc['product_id']

                if product_id.bom_ids and product_id.bom_ids.bom_line_ids:
                    group_product_components.append((0,0,{'product_id': product_id.id,'qty': lc['qty'] }) )
                    # lc['line'].unlink()
                    for component in product_id.bom_ids.bom_line_ids:
                        qty_production = (product_id.bom_ids.product_qty*component.product_qty) * lc['qty']
                        qty_stock = component.product_id.qty_available
                        qty = 0 if qty_stock > 0 else qty_production - qty_stock

                        group_product_components.append((0,0,{
                            'subproduct_id': component.product_id.id,
                            'qty_production': qty_production,
                            'qty_stock': qty_stock,
                            #'qty': qty,
                            'area': component.product_id.bom_ids.area,
                        }))

                        #Receta 2 de (sub 2)
                        if component.product_id.bom_ids and component.product_id.bom_ids.bom_line_ids:
                            for component1 in component.product_id.bom_ids.bom_line_ids:
                                qty1_production = qty_production * component1.product_qty
                                qty1_stock = component1.product_id.qty_available
                                qty1 = 0 if qty_stock else qty1_production - qty1_stock
                                group_product_components.append((0,0,{
                                    'subproduct1_id': component1.product_id.id,
                                    'qty_production': qty1_production,
                                    'qty_stock': qty1_stock,
                                    #'qty': qty1,
                                    'area': component.product_id.bom_ids.area,
                                }))

                                #Receta 3 de (sub 3)
                                if component1.product_id.bom_ids and component1.product_id.bom_ids.bom_line_ids:
                                    for component2 in component1.product_id.bom_ids.bom_line_ids:
                                        qty2_production = qty1_production * component2.product_qty
                                        qty2_stock = component2.product_id.qty_available
                                        qty2 = 0 if qty1_stock > 0 else qty2_production - qty2_stock

                                        group_product_components.append((0,0,{
                                            'subproduct2_id': component2.product_id.id,
                                            'qty_production': qty2_production,
                                            'qty_stock': qty2_stock,
                                            #'qty': qty2,
                                            'area': component.product_id.bom_ids.area,
                                        }))

                                        #Receta 4 de (sub 4)
                                        if component2.product_id.bom_ids and component2.product_id.bom_ids.bom_line_ids:
                                            for component3 in component2.product_id.bom_ids.bom_line_ids:
                                                qty3_production = qty2_production * component3.product_qty
                                                qty3_stock = component3.product_id.qty_available
                                                qty3 = 0 if qty2_stock > 0 else qty3_production - qty3_stock

                                                group_product_components.append((0,0,{
                                                    'subproduct3_id': component3.product_id.id,
                                                    'qty_production': qty3_production,
                                                    'qty_stock': qty3_stock,
                                                    #'qty': qty3,
                                                    'area': component.product_id.bom_ids.area,
                                                }))
                                                #Receta 5 de (sub 5)
                                                if component3.product_id.bom_ids and component3.product_id.bom_ids.bom_line_ids:
                                                    for component4 in component3.product_id.bom_ids.bom_line_ids:
                                                        qty4_production = qty3_production * component4.product_qty
                                                        qty4_stock = component3.product_id.qty_available
                                                        qty4 = 0 if qty3_stock > 0 else qty4_production - qty4_stock

                                                        group_product_components.append((0,0,{
                                                            'subproduct4_id': component4.product_id.id,
                                                            'qty_production': qty4_production,
                                                            'qty_stock': qty4_stock,
                                                            #'qty': qty4,
                                                            'area': component.product_id.bom_ids.area,
                                                        }))

                self.write({'product_ids': group_product_components})
        return True

    def confirm_planning(self):
        for p in self:
            if p.product_ids:
                group_product_components = []
                dic_components = {}
                for line in p.product_ids:
                    if line.subproduct_id:
                        if line.area not in dic_components:
                            dic_components[line.area] = []

                        dic_components[line.area].append((0,0, {
                            'product_id': line.subproduct_id.id,
                            'quantity': line.qty,
                        }))

                if len(dic_components) > 0:
                    for component in dic_components:
                        op_lot_id = self.env['quemen.op_lote'].create({
                            'date': p.date,
                            'date_mrp_production': p.planning_date,
                            'reference': p.name,
                            'product_ids': dic_components[component]})
            p.write({'state': "confirmado"})
        return True

class QuemenPlanningLine(models.Model):
    _name = "quemen.planning_line"
    _description = " . "
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = "product_id"

    planning_id = fields.Many2one("quemen.planning", "Planeacion")
    product_id = fields.Many2one('product.product', 'Producto', tracking=True)
    subproduct_id = fields.Many2one('product.product', 'Componente', tracking=True)
    subproduct1_id = fields.Many2one('product.product', 'Componente1', tracking=True)
    subproduct2_id = fields.Many2one('product.product', 'Componente2', tracking=True)
    subproduct3_id = fields.Many2one('product.product', 'Componente3', tracking=True)
    subproduct4_id = fields.Many2one('product.product', 'Componente4', tracking=True)
    qty_production = fields.Float('Producción', tracking=True)
    qty_stock = fields.Float('Existencia', tracking=True)
    qty = fields.Float('Cantidad', tracking=True)
    parent_line_id = fields.Many2one("quemen.planning_line", "Linea padre")

    # FIX: related -> no selection. Hereda el selection del campo origen (planning_id.state)
    line_state = fields.Selection(related='planning_id.state', string='Estado', store=True, readonly=True)

    area = fields.Char("Area")

    # @api.onchange('product_id')
    # def _onchange_product_id(self):
    #     if self.product_id and self.product_id.bom_ids:
    #         for line in self.product_id.bom_ids.bom_line_ids:
    #             pline_dic = {
    #                 'subproduct_id': line.product_id.id,
    #                 'qty_production': 0,
    #                 'qty_stock': 0,
    #                 'parent_line_id': self.id,
    #                 'planning_id': self.planning_id.id,
    #             }
    #             new_line_id = self.env['quemen.planning_line'].create(pline_dic)
