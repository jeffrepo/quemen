from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMrpProductionStage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.child, cls.parent_one, cls.parent_three = cls.env['product.product'].create([
            {'name': name, 'type': 'product'}
            for name in ('Stage child', 'Stage parent one', 'Stage parent three')
        ])
        cls.child_bom = cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.child.product_tmpl_id.id,
            'product_uom_id': cls.child.uom_id.id,
            'product_qty': 1,
        })
        cls.env['mrp.bom'].create([
            {
                'product_tmpl_id': parent.product_tmpl_id.id,
                'product_uom_id': parent.uom_id.id,
                'product_qty': 1,
                'bom_line_ids': [(0, 0, {
                    'product_id': cls.child.id,
                    'product_qty': 1,
                    'product_uom_id': cls.child.uom_id.id,
                    'stage': stage,
                })],
            }
            for parent, stage in (
                (cls.parent_one, 1),
                (cls.parent_three, 3),
            )
        ])

    def _production(self, **extra_values):
        values = {
            'product_id': self.child.id,
            'product_qty': 1,
            'product_uom_id': self.child.uom_id.id,
            'bom_id': self.child_bom.id,
        }
        values.update(extra_values)
        return self.env['mrp.production'].create(values)

    def test_new_order_uses_highest_used_in_stage(self):
        production = self._production()

        self.assertEqual(production.x_studio_etapa, 3)
        self.assertEqual(production.quemen_etapa_kanban, '3')

    def test_explicit_stage_is_preserved(self):
        production = self._production(x_studio_etapa=2)

        self.assertEqual(production.x_studio_etapa, 2)

    def test_sync_corrects_only_orders_at_default_stage(self):
        default_production = self._production(x_studio_etapa=0)
        manual_production = self._production(x_studio_etapa=2)

        self.env['mrp.production'].sync_open_stages_from_bom()

        self.assertEqual(default_production.x_studio_etapa, 3)
        self.assertEqual(default_production.quemen_etapa_kanban, '3')
        self.assertEqual(manual_production.x_studio_etapa, 2)
