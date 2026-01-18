# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from re import findall as regex_findall
from re import split as regex_split

from operator import attrgetter
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ProductionLot(models.Model):
    #_inherit = 'stock.production.lot'
    _inherit = 'stock.lot'

    elaboration_date = fields.Date('Fecha de elaboración')
    

    @api.model
    def get_available_lots_for_pos(self):
        product_ids = self.env['product.product'].search([
            ('available_in_pos', '=', True),
        ]).ids
    
        StockQuant = self.env['stock.quant']
        lots = StockQuant.read_group(
            domain=[
                ('product_id', 'in', product_ids),
                ('location_id.usage', '=', 'internal'),
                ('quantity', '>', 0),
                ('lot_id', '!=', False),
                ('x_studio_categoria_de_producto', '!=', "Rebanadas"),
            ],
            fields=['lot_id'],
            groupby=['lot_id']
        )
        lot_ids = [group['lot_id'][0] for group in lots if group['lot_id']]
        lot_objs = self.browse(lot_ids)
        return {
            lot.name: {
                'id': lot.id,
                'product_id': lot.product_id.id
            }
            for lot in lot_objs
        }
