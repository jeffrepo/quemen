# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import datetime
import math
import re
import warnings

from collections import defaultdict
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round, float_is_zero, format_datetime
from odoo.tools.misc import OrderedSet, format_date, groupby as tools_groupby

from odoo.addons.stock.models.stock_move import PROCUREMENT_PRIORITIES
import logging
SIZE_BACK_ORDER_NUMERING = 3

class MrpProduction(models.Model):
    """ Manufacturing Orders """
    _inherit = 'mrp.production'

    # lot_id = fields.Many2one('quemen.op_lote','Lote')

    
    @api.depends('company_id', 'bom_id', 'product_id', 'product_qty', 'product_uom_id', 'location_src_id', 'never_product_template_attribute_value_ids')
    def _compute_move_raw_ids(self):
        res = super(MrpProduction, self)._compute_move_raw_ids()
        for line in self.move_raw_ids:
            if len(line.product_id.bom_ids) > 0:
                if line.product_id.bom_ids[0].picking_type_id:
                    line.location_id = line.product_id.bom_ids[0].picking_type_id.default_location_dest_id.id

    def _get_move_raw_values(self, product_id, product_uom_qty, product_uom, operation_id=False, bom_line=False):
        res = super(MrpProduction, self)._get_move_raw_values(product_id, product_uom_qty, product_uom, operation_id, bom_line)
        if res:
            if ('location_id' and 'product_id') in res and (bom_line and bom_line.location_src_id):
                res['location_id'] = bom_line.location_src_id.id if (bom_line and bom_line.location_src_id) else False,
        return res

    def elminar_lineas_duplicadas(self):
        listas = self.env['mrp.bom'].search([('active','=',True)])
        listas_guardadas = []
        listas_eliminadas = []
        for l in listas:
            listas_guardadas.append(l)
        lineas_eliminar = []
        if listas_guardadas:
            for lista in listas_guardadas:
                if len(lista.bom_line_ids) > 0:
                    bom_line = lista.bom_line_ids
                    for linea in bom_line:
                        if linea.id not in listas_eliminadas:
                            producto = linea.product_id.id
                            linea_id = linea.id
                            linea_eliminar = self.env['mrp.bom.line'].search([('id','!=', linea.id),('product_id','=', linea.product_id.id),('bom_id','=', linea.bom_id.id)])
                            if len(linea_eliminar) > 0:
                                for l in linea_eliminar:
                                    listas_eliminadas.append(l.id)
                                    l.unlink()
