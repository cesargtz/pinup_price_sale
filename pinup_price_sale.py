# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions
import psycopg2
import logging

_logger = logging.getLogger(__name__)

class pinup_price_purchase(models.Model):
    _inherit = ['mail.thread']
    _name = 'pinup.price.sale'

    name = fields.Char('Set Price Reference', required=True, select=True, copy=False, default=lambda self: self.env['ir.sequence'].next_by_code('reg_code_price_sale'), help="Unique number of the set prices")
    sale_order_id = fields.Many2one('sale.order')
    partner_id = fields.Many2one(
        'res.partner', readonly=True, related="sale_order_id.partner_id", store=True)
    tons_contract = fields.Float(compute="_compute_tons",digits=(12, 4))
    request_date = fields.Date(required=True, default=fields.Date.today)
    pinup_tons = fields.Float(required=True, eval="False")
    price_bushel = fields.Float(digits=(12, 2))
    bases_ton = fields.Float(digits=(12, 2))
    price_min = fields.Float(digits=(12, 2))
    service = fields.Float(digits=(12, 4))
    tc = fields.Float(digits=(12, 4))
    price_per_ton = fields.Float(compute="_compute_ton_usd", store=True, digits=(12, 2))
    price_mxn = fields.Float(compute="_compute_mx", store=True, digits=(12, 2))
    tons_outlet = fields.Float(
        compute="_compute_to")
    # tons_invoiced = fields.Float(
    #     compute="_compute_ti", digits=(12, 3),  store=True)
    tons_priced = fields.Float(
        compute="_compute_priced", digits=(12, 3))
    invoice_create_id = fields.Many2one('account.invoice', readonly=True)
    invoice_service_id = fields.Many2one('account.invoice', readonly=True)


    contract_type = fields.Selection([
        ('axc', 'AxC'),
        ('pf', 'Precio Fijo'),
        ('pm', 'Precio Maximo'),
        ('pd', 'Precio Despues'),
        ('sv', 'Servicios'),
        ('na', 'No aplica'),
    ], 'Tipo de contrato', readonly=True, compute="_compute_contract_type", store=True, default='na')


    state = fields.Selection([
        ('draft', "Draft"),
        ('price', "Price"),
        ('currency', "Currency"),
        ('invoiced', "Invoiced"),
        ('close', "Close"),
    ], default='draft')



    @api.one
    @api.depends("sale_order_id")
    def _compute_tons(self):
        qty = 0
        for line in self.sale_order_id.order_line:
            qty = qty + line.product_uom_qty
        self.tons_contract = qty

    @api.one
    @api.depends("sale_order_id")
    def _compute_contract_type(self):
        self.contract_type = self.sale_order_id.contract_type

    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_confirmed(self):
        self.state = 'price'


    # @api.constrains('pinup_tons')
    # def _check_tons(self):
    #     tons_available = self.tons_outlet + self.pinup_tons - self.tons_priced
    #     if self.pinup_tons > tons_available:
    #         raise exceptions.ValidationError(
    #             "No tienes las suficientes toneladas para preciar.")

    # @api.multi
    # @api.depends('sale_order_id')
    # def _compute_ti(self):
    #     tons_billing = 0
    #     if self.sale_order_id.invoice_ids[0]:
    #         for invoice in self.sale_order_id.invoice_ids:
    #             if invoice.state in ('open', 'paid'):
    #                 tons_billing += invoice.tons
    #         self.tons_invoiced = tons_billing
    #     else:
    #         self.tons_invoiced = 0
    #
    @api.one
    @api.depends('sale_order_id')
    def _compute_to(self):
        for line in self.env['truck.outlet'].search([('contract_id', '=', self.sale_order_id.name), ('state', '=', 'done')]):
            self.tons_outlet += line['raw_kilos'] / 1000
        for line in self.env['wagon.outlet'].search([('contract_id', '=', self.sale_order_id.name), ('state', '=', 'done')]):
            self.tons_outlet += line['raw_kilos'] / 1000

    @api.one
    @api.depends('sale_order_id')
    def _compute_priced(self):
        for line in self.env['pinup.price.sale'].search([('sale_order_id', '=', self.sale_order_id.name)]):
            self.tons_priced += line.pinup_tons
    @api.one
    @api.depends('price_bushel')
    def _compute_ton_usd(self):
            self.price_per_ton = self.price_bushel * 0.3936825 + self.bases_ton

    @api.one
    @api.depends('price_per_ton','tc')
    def _compute_mx(self):
        if self.price_per_ton >= self.price_min:
            self.price_mxn = self.price_per_ton * self.tc
        else:
            self.price_mxn = self.price_min * self.tc

    @api.multi
    def write(self, vals, recursive=None):
        if not recursive:
            if self.state == 'draft':
                self.write({'state': 'price'}, 'r')
            elif self.state == 'price':
                self.write({'state': 'currency'}, 'r')
            elif self.state == 'currency':
                self.write({'state': 'invoiced'}, 'r')
        res = super(pinup_price_purchase, self).write(vals)
        return res

    @api.model
    def create(self, vals):
        vals['state'] = 'price'
        res = super(pinup_price_purchase, self).create(vals)
        return res

    @api.multi
    def action_create(self):
        invoice_id = self.env['account.invoice'].create({
            'partner_id' : self.partner_id.id,
            'account_id' : self.partner_id.property_account_receivable_id.id,
            'journal_id' : self.env['account.journal'].search([('type','=','sale')], order='id', limit=1).id,
            'currency_id' : 34,
            'type':'out_invoice',
            'origin' : self.sale_order_id.name,
            'date_invoice':self.request_date,
            'state':'draft',
            })
        self.create_move_id(invoice_id)
        self.invoice_create_id = invoice_id
        if self.service > 0:
            self.create_service()
        self.state = 'close'


    @api.multi
    def create_move_id(self, invoice_id):
        product = self.sale_order_id.order_line.product_id
        # iva = product.product_tmpl_id.supplier_taxes_id.id
        # _logger.critical(product.product_tmpl_id.supplier_taxes_id.id ) 202
        move_id = self.env['account.invoice.line'].create({
            'invoice_id': invoice_id.id,
            'origin': self.sale_order_id.name,
            'price_unit': self.price_mxn,
            'product_id': product[0].id,
            'quantity' : self.pinup_tons,
            'uom_id' : 7,
            'account_id': self.env['account.account'].search([('code','=','111211')]).id,
            'name':product[0].product_tmpl_id.description_sale,
            'company_id':1,
        })

    @api.multi
    def create_service(self, x):
        invoice_id = self.env['account.invoice'].create({
            'partner_id' : self.partner_id.id,
            'account_id' : self.partner_id.property_account_receivable_id.id,
            'journal_id' : self.env['account.journal'].search([('type','=','sale')], order='id', limit=1).id,
            'currency_id' : 34,
            'type':'out_invoice',
            'origin' : self.sale_order_id.name,
            'date_invoice':self.request_date,
            'state':'draft',
            })
        self.service_move_id(invoice_id)
        self.invoice_service_id= invoice_id


    @api.multi
    def service_move_id(self, invoice_id):
        move_id = self.env['account.invoice.line'].create({
            'invoice_id': invoice_id.id,
            'origin': self.sale_order_id.name,
            'price_unit': self.service,
            'product_id': 202,
            'quantity' : self.pinup_tons,
            'uom_id' : 7,
            'account_id': self.env['account.account'].search([('code','=','182122')]).id,
            'name':'SERVICIO DE ELEVACIÓN',
            'company_id':1,
        })

        # self.env.cr.execute('INSERT INTO account_invoice_line_tax VALUES (%s, %s)',(move_id.id, iva))
