# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class AccountAccount(models.Model):
    _name = "account.account"

    segmento = fields.Integer('Segmento')
