from openerp import fields, models, api
import logging
logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = 'sale.order'

    pinup_sale_count = fields.Integer(compute="_compute_pinup_sale_count")

    @api.multi
    def pinup_price(self):
        self.ensure_one()
        try:
            form_id = self.env['ir.model.data'].get_object_reference('pinup_price_sale', 'pinup_price_sale_form_view')[1]
        except ValueError:
            form_id = False

        ctx = dict()
        ctx.update({
            'default_sale_order_id': self.ids[0],
        })
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'pinup.price.sale',
            'views': [(form_id, 'form')],
            'view_id': form_id,
            #'target': 'new',
            'context': ctx,
        }

    # Buttons
    # Preciaciones
    @api.multi
    def _compute_pinup_sale_count(self):
        for pinup in self:
            count = 0
            for itr in self.env['pinup.price.sale'].search([('sale_order_id.id','=', self.id)]):
                count = count + 1
        self.pinup_sale_count = count

    @api.multi
    def pinup_price_sale_tree(self):
        tree_res = self.env['ir.model.data'].get_object_reference('pinup_price_sale', 'pinup_price_sale_tree_view')
        tree_id = tree_res and tree_res[1] or False
        form_res = self.env['ir.model.data'].get_object_reference('pinup_price_sale', 'pinup_price_sale_form_view')
        form_id = form_res and form_res[1] or False

        return{
            'type'          :   'ir.actions.act_window',
            'view_type'     :   'form', #Tampilan pada tabel pop-up
            'view_mode'     :   'tree,form', # Menampilkan bagian yang di pop up, tree = menampilkan tabel tree nya utk product
            'res_model'     :   'pinup.price.sale', #Menampilkan tabel yang akan di show di pop-up screen
            'target'        :   'new', # Untuk menjadikan tampilan prduct yang dipilih menjadi pop-up table tampilan baru, jika dikosongin maka tidak muncul pop-up namun muncul halaman baru.
            'views'         :   [(tree_id, 'tree'),(form_id, 'form')],
            'domain'        :   [('sale_order_id.id','=', self.id)] #Filter id barang yang ditampilkan
            }
