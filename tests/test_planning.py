from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPlanning(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product_a, cls.product_a2, cls.product_b, cls.raw = (
            cls.env['product.product'].create([
                {'name': name, 'type': 'product'}
                for name in ('Planning A', 'Planning A2', 'Planning B', 'Raw')
            ])
        )
        cls.boms = cls.env['mrp.bom'].create([
            {
                'product_tmpl_id': product.product_tmpl_id.id,
                'product_uom_id': product.uom_id.id,
                'product_qty': 1,
                'area': area,
                'bom_line_ids': [(0, 0, {
                    'product_id': cls.raw.id,
                    'product_qty': 1,
                    'product_uom_id': cls.raw.uom_id.id,
                })],
            }
            for product, area in (
                (cls.product_a, 'A'), (cls.product_a2, 'A'), (cls.product_b, 'B'),
            )
        ])

    def _planning(self, lines):
        return self.env['quemen.planning'].create({
            'date': date(2026, 9, 21),
            'planning_date': date(2026, 9, 22),
            'product_ids': [(0, 0, values) for values in lines],
        })

    def _lots(self, planning):
        return self.env['quemen.op_lote'].search([
            ('reference', '=', planning.name),
        ])

    def _contents(self, lots):
        return sorted(
            sorted((line.product_id.id, line.quantity) for line in lot.product_ids)
            for lot in lots
        )

    def test_groups_by_area_and_column_only_with_bom(self):
        lines = []
        expected = []
        for quantity, column in enumerate((
            'product_id', 'subproduct_id', 'subproduct1_id',
            'subproduct2_id', 'subproduct3_id', 'subproduct4_id',
        ), start=1):
            for product, area in (
                (self.product_a, 'A'), (self.product_a2, 'A'),
                (self.product_b, 'B'), (self.raw, 'A'),
            ):
                lines.append({column: product.id, 'qty': quantity, 'area': area})
            expected.extend([
                [(self.product_a.id, quantity), (self.product_a2.id, quantity)],
                [(self.product_b.id, quantity)],
            ])
        planning = self._planning(lines)

        self.assertTrue(planning.confirm_planning())

        lots = self._lots(planning)
        self.assertEqual(len(lots), 12)
        self.assertEqual(self._contents(lots), sorted(expected))
        self.assertEqual(planning.state, 'confirmado')
        for lot in lots:
            self.assertEqual(lot.date, planning.date)
            self.assertEqual(lot.date_mrp_production, planning.planning_date)
            self.assertEqual(lot.state, 'borrador')

    def test_uses_bom_area_when_line_area_is_empty(self):
        planning = self._planning([
            {'product_id': self.product_a.id, 'qty': 2},
            {'product_id': self.product_a2.id, 'qty': 3},
            {'product_id': self.product_b.id, 'qty': 4},
        ])

        planning.confirm_planning()

        self.assertEqual(self._contents(self._lots(planning)), sorted([
            [(self.product_a.id, 2), (self.product_a2.id, 3)],
            [(self.product_b.id, 4)],
        ]))

    def test_explicit_line_area_takes_precedence(self):
        planning = self._planning([
            {'subproduct1_id': self.product_a.id, 'qty': 2, 'area': 'Manual'},
            {'subproduct1_id': self.product_b.id, 'qty': 3, 'area': 'Manual'},
        ])

        planning.confirm_planning()

        self.assertEqual(self._contents(self._lots(planning)), [
            [(self.product_a.id, 2), (self.product_b.id, 3)],
        ])

    def test_all_populated_columns_in_one_line_are_included(self):
        planning = self._planning([{
            'product_id': self.product_a.id,
            'subproduct_id': self.product_a2.id,
            'subproduct4_id': self.product_b.id,
            'qty': 2.5,
            'area': 'A',
        }])

        planning.confirm_planning()

        self.assertEqual(self._contents(self._lots(planning)), sorted([
            [(self.product_a.id, 2.5)],
            [(self.product_a2.id, 2.5)],
            [(self.product_b.id, 2.5)],
        ]))

    def test_calculated_hierarchy_uses_each_child_bom_area(self):
        products = self.env['product.product'].create([
            {'name': 'Planning level %s' % level, 'type': 'product'}
            for level in range(6)
        ])
        areas = ('A', 'B', 'A', 'B', 'A', 'B')
        for level in reversed(range(6)):
            product = products[level]
            child = products[level + 1] if level < 5 else self.raw
            self.env['mrp.bom'].create({
                'product_tmpl_id': product.product_tmpl_id.id,
                'product_uom_id': product.uom_id.id,
                'product_qty': 1,
                'area': areas[level],
                'bom_line_ids': [(0, 0, {
                    'product_id': child.id,
                    'product_qty': 1,
                    'product_uom_id': child.uom_id.id,
                })],
            })
        planning = self._planning([{'product_id': products[0].id, 'qty': 2}])

        planning.show_components()

        columns = (
            'product_id', 'subproduct_id', 'subproduct1_id',
            'subproduct2_id', 'subproduct3_id', 'subproduct4_id',
        )
        self.assertEqual(len(planning.product_ids), 6)
        for level, column in enumerate(columns):
            line = planning.product_ids.filtered(lambda line: line[column])
            self.assertEqual(line[column], products[level])
            self.assertEqual(line.area, areas[level])
        planning.product_ids.write({'qty': 2})

        planning.confirm_planning()

        self.assertEqual(self._contents(self._lots(planning)), [
            [(product.id, 2)] for product in products
        ])

    def test_no_empty_lots_without_eligible_products(self):
        empty = self._planning([])
        without_bom = self._planning([
            {'product_id': self.raw.id, 'qty': 2, 'area': 'A'},
            {'subproduct4_id': self.raw.id, 'qty': 3, 'area': 'B'},
        ])

        (empty | without_bom).confirm_planning()

        for planning in empty | without_bom:
            self.assertFalse(self._lots(planning))
            self.assertEqual(planning.state, 'confirmado')

    def test_confirming_twice_does_not_duplicate_lots(self):
        planning = self._planning([
            {'product_id': self.product_a.id, 'qty': 2},
        ])
        planning.confirm_planning()
        lots = self._lots(planning)
        self.assertEqual(len(lots), 1)

        planning.confirm_planning()

        self.assertEqual(self._lots(planning), lots)

    def test_plannings_are_not_merged(self):
        first = self._planning([
            {'subproduct_id': self.product_a.id, 'qty': 2, 'area': 'A'},
        ])
        second = self._planning([
            {'subproduct_id': self.product_a2.id, 'qty': 3, 'area': 'A'},
        ])

        (first | second).confirm_planning()

        self.assertEqual(self._contents(self._lots(first)), [[(self.product_a.id, 2)]])
        self.assertEqual(self._contents(self._lots(second)), [[(self.product_a2.id, 3)]])

    def test_archived_and_other_company_boms_are_excluded(self):
        self.boms[0].active = False
        other_company = self.env['res.company'].create({'name': 'Planning other company'})
        self.boms[1].company_id = other_company
        planning = self._planning([
            {'product_id': self.product_a.id, 'qty': 2},
            {'subproduct_id': self.product_a2.id, 'qty': 3},
            {'subproduct4_id': self.product_b.id, 'qty': 4},
        ])

        planning.confirm_planning()

        self.assertEqual(self._contents(self._lots(planning)), [[(self.product_b.id, 4)]])
