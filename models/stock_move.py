# -*- coding: utf-8 -*-
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError, ValidationError
import logging
import pytz
from datetime import datetime

class StockMove(models.Model):
    _inherit = "stock.move"

    generar_nuevos_lotes = fields.Boolean(string="Generar nuevos lotes")

    def _actualizar_cantidades(self, cantidad):
        lot_ids = self.env["stock.lot"].search([("name","!=", "0000000"),("product_qty", ">", 0)])
        logging.warning(len(lot_ids))
        quant_ids = self.env["stock.quant"].search([("location_id","=", 357),("lot_id","in", lot_ids.ids)])
        logging.warning(len(quant_ids))
        contador = 0
        for m in quant_ids:
            if contador <= cantidad:
                logging.warning(m)
                logging.warning("cantidad")
                nuevo_quant_id = self.env["stock.quant"].with_context(inventory_mode=True).sudo().create({
                    'location_id': 357,
                    'product_id': m.product_id.id,
                    'lot_id': m.lot_id.id,
                    'inventory_quantity': 0,
                }).action_apply_inventory()
                #logging.warning(m.inventory_quantity_auto_apply)
                m.write({"available_quantity": 0})
                logging.warning(contador)
                contador += 1
        return True
        
    def _search_picking_for_assignation(self):
        res = super(StockMove, self)._search_picking_for_assignation()
        res = False
        return res

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    barcode = fields.Char('Código de barra')
    cantidad_etiquetas = fields.Float('Cantidad etiquetas')

    @api.onchange('barcode')
    def _onchange_barcode(self):
        for line in self:
            if line.barcode:
                lot_id = self.env['stock.lot'].search([('name','=',line.barcode)])
                if len(lot_id) > 0:
                    lot_info = False
                    if len(lot_id) == 1:
                        lot_info = lot_id[0]
                    if len(lot_id) > 1:
                        for lot in lot_id:
                            if lot.product_id.producto_porciones:
                                lot_info = lot
                    line.product_id = lot_info.product_id.id
                    line.lot_id = lot_info.id
                    line.qty_done = 1
                else:
                    raise ValidationError(_("Código de barra inválido"))
