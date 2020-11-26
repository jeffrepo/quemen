# -*- encoding: utf-8 -*-

from openerp import models, fields, api, _
from odoo.exceptions import UserError
import logging

class PosOrder(models.Model):
    _inherit = 'pos.order'

    def deshabilitar_cupon(self,cupon):
        logging.warn(cupon)
        cupon_id = self.env['sale.coupon'].search([('id','=',cupon)])
        if cupon_id:
            cupon_id.write({'state': 'used'})
        return True

    def habilitar_cupon(self,cupon):
        logging.warn(cupon)
        cupon_id = self.env['sale.coupon'].search([('code','=',str(cupon))])
        if cupon_id:
            cupon_id.write({'state': 'new'})
        return True
