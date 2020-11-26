# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _

class PosConfig(models.Model):
    _inherit = 'pos.config'

    efectivo_maximo = fields.Float(string="Efectivo máxmio")
    cupones = fields.Boolean('Cupones')
