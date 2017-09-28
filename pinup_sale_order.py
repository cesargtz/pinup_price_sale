from openerp import fields, models, api
import logging
logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = 'sale.order'

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
