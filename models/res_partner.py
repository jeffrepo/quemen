# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _

class ResPartner(models.Model):
    _inherit = 'res.partner'

    location_desti_id = fields.Many2one("stock.location", string="Ubicación destino")
