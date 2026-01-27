# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    area = fields.Char(string='Area')


class MrpBomLine(models.Model):
    """ Defines bills of material for a product or a product template """
    _inherit = 'mrp.bom.line'
    _order = "stage asc"

    stage = fields.Integer(string='Etapa')
    location_src_id = fields.Many2one('stock.location', string='Ubicación origen')

