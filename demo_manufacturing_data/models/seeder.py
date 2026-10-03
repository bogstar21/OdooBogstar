# -*- coding: utf-8 -*-
import random
from datetime import timedelta

from odoo import fields, models

# Raw materials: (name, cost, sales uom qty per purchase, default vendor cost)
RAW_MATERIALS = [
    "Tabla de Pino 2m",
    "Tabla de Roble 2m",
    "Pack Tornillos (100u)",
    "Bote de Barniz 1L",
    "Juego de Patas Metálicas",
    "Tela de Tapicería (m²)",
    "Bloque de Espuma",
    "Riel de Cajón (par)",
    "Bisagra de Armario (par)",
    "Tablero Aglomerado",
]

# Finished goods: (name, sale price, [(component name, qty), ...])
FINISHED_GOODS = [
    ("Mesa de Comedor Roble", 420.0, [
        ("Tabla de Roble 2m", 4), ("Juego de Patas Metálicas", 1),
        ("Pack Tornillos (100u)", 1), ("Bote de Barniz 1L", 1),
    ]),
    ("Estantería de Pino", 180.0, [
        ("Tabla de Pino 2m", 6), ("Pack Tornillos (100u)", 1), ("Bote de Barniz 1L", 1),
    ]),
    ("Escritorio Clásico", 250.0, [
        ("Tablero Aglomerado", 3), ("Juego de Patas Metálicas", 1), ("Pack Tornillos (100u)", 1),
    ]),
    ("Sillón Tapizado", 310.0, [
        ("Bloque de Espuma", 1), ("Tela de Tapicería (m²)", 2), ("Pack Tornillos (100u)", 1),
    ]),
    ("Mueble de Cocina", 390.0, [
        ("Tablero Aglomerado", 2), ("Bisagra de Armario (par)", 2), ("Pack Tornillos (100u)", 1),
    ]),
    ("Taburete de Bar Madera", 95.0, [
        ("Tabla de Pino 2m", 2), ("Pack Tornillos (100u)", 1), ("Bote de Barniz 1L", 1),
    ]),
    ("Escritorio Ejecutivo Deluxe", 540.0, [
        ("Tabla de Roble 2m", 2), ("Juego de Patas Metálicas", 1),
        ("Bote de Barniz 1L", 1), ("Pack Tornillos (100u)", 1),
    ]),
    ("Cómoda 3 Cajones", 280.0, [
        ("Tablero Aglomerado", 2), ("Riel de Cajón (par)", 3), ("Pack Tornillos (100u)", 1),
    ]),
]

VENDOR_NAMES = [
    "Maderas del Norte S.L.", "Ferretería Industrial Ibérica", "Barnices y Acabados Castilla",
    "Metalurgia Vasca S.A.", "Textiles del Sur S.L.", "Espumas y Rellenos Catalunya",
    "Suministros Aglomerados Valencia", "Herrajes Mediterráneo", "Transportes Madera Rápida",
    "Química Industrial Aragón", "Accesorios Mobiliario Galicia", "Importadora Textil Europea",
]

COMPANY_CUSTOMER_NAMES = [
    "Muebles Hogar Feliz", "Decoraciones Castro", "Oficinas Modernas S.L.", "Interiorismo Bilbao",
    "Contract Hotelero Costa Brava", "Mobiliario Escolar Andalucía", "Cadena Restaurantes El Roble",
    "Retail Home Ibérica", "Espacios de Trabajo Coworking", "Residencial Los Álamos",
    "Clínica Dental Sonrisa", "Hotel Rural Pirineos", "Academia de Negocios Madrid",
    "Constructora Ribera del Duero", "Muebles Export Portugal",
]

INDIVIDUAL_CUSTOMER_NAMES = [
    "Marta Fernández Ruiz", "Javier López Gómez", "Carmen Sánchez Díaz", "Antonio Martín Pérez",
    "Lucía Romero Vidal", "Pablo Navarro Castro", "Elena Jiménez Ortiz", "Diego Molina Reyes",
    "Sara Torres Blanco", "Álvaro Gil Moreno",
]

CITIES = ["Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao", "Zaragoza", "Málaga", "Murcia"]


class DemoManufacturingSeeder(models.TransientModel):
    """Settings ▸ Technical ▸ Demo Data ▸ Generate Manufacturing Company.

    A practice-environment tool: populates vendors, customers, products with
    BOMs, purchase/manufacturing/sales orders in a realistic mix of states.
    Best-effort by design — each order/MO is wrapped individually so one
    failure (e.g. insufficient stock to deliver) just gets skipped and
    counted, instead of aborting the whole run, since the point is bulk
    volume to practice on, not strict correctness of every record.
    """
    _name = "demo.manufacturing.seeder"
    _description = "Demo Manufacturing Company Seeder"

    result_log = fields.Text(readonly=True)

    def action_generate(self):
        self.ensure_one()
        log = []

        vendors = self._create_partners(VENDOR_NAMES, supplier=True, companies_only=True)
        log.append("Vendors created: %d" % len(vendors))

        customers = self._create_partners(COMPANY_CUSTOMER_NAMES, customer=True, companies_only=True)
        customers |= self._create_partners(INDIVIDUAL_CUSTOMER_NAMES, customer=True, companies_only=False)
        log.append("Customers created: %d" % len(customers))

        raw_variants = self._create_raw_materials()
        log.append("Raw material products created: %d" % len(raw_variants))

        finished_variants, bom_count = self._create_finished_goods(raw_variants)
        log.append("Finished good products created: %d (with %d BOMs)" % (len(finished_variants), bom_count))

        self._seed_raw_material_stock(raw_variants)
        log.append("Seeded on-hand stock for every raw material (500 units each)")

        po_done, po_failed = self._create_purchase_orders(vendors, raw_variants)
        log.append("Purchase orders created: %d (%d confirmed, %d left in other states/failed)" % (
            po_done["total"], po_done["confirmed"], po_failed))

        mo_done, mo_failed = self._create_manufacturing_orders(finished_variants)
        log.append("Manufacturing orders created: %d (%d completed, %d confirmed only, %d failed)" % (
            mo_done["total"], mo_done["completed"], mo_done["confirmed_only"], mo_failed))

        so_stats, so_failed = self._create_sales_orders(customers, finished_variants)
        log.append(
            "Sales orders created: %d (%d confirmed, %d delivered, %d invoiced, %d failed)" % (
                so_stats["total"], so_stats["confirmed"], so_stats["delivered"],
                so_stats["invoiced"], so_failed)
        )

        self.result_log = "\n".join(log)
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name, "res_id": self.id,
            "view_mode": "form", "target": "new",
        }

    # ------------------------------------------------------------------
    # Partners
    # ------------------------------------------------------------------
    def _create_partners(self, names, supplier=False, customer=False, companies_only=True):
        Partner = self.env["res.partner"]
        spain = self.env.ref("base.es", raise_if_not_found=False)
        created = Partner
        for name in names:
            vals = {
                "name": name,
                "is_company": companies_only,
                "city": random.choice(CITIES),
                "country_id": spain.id if spain else False,
                "supplier_rank": 1 if supplier else 0,
                "customer_rank": 1 if customer else 0,
            }
            created |= Partner.create(vals)
        return created

    # ------------------------------------------------------------------
    # Products
    # ------------------------------------------------------------------
    def _create_raw_materials(self):
        ProductTemplate = self.env["product.template"]
        uom_unit = self.env.ref("uom.product_uom_unit")
        categ = self._get_or_create_category("Materias Primas")
        variants = {}
        for name in RAW_MATERIALS:
            template = ProductTemplate.create({
                "name": name,
                "type": "consu",
                "is_storable": True,
                "categ_id": categ.id,
                "uom_id": uom_unit.id,
                "uom_po_id": uom_unit.id,
                "standard_price": round(random.uniform(2.0, 40.0), 2),
                "list_price": round(random.uniform(5.0, 60.0), 2),
                "purchase_ok": True,
                "sale_ok": False,
            })
            variants[name] = template.product_variant_id
        return variants

    def _create_finished_goods(self, raw_variants):
        ProductTemplate = self.env["product.template"]
        Bom = self.env["mrp.bom"]
        uom_unit = self.env.ref("uom.product_uom_unit")
        categ = self._get_or_create_category("Productos Terminados")
        variants = {}
        bom_count = 0
        for name, price, components in FINISHED_GOODS:
            template = ProductTemplate.create({
                "name": name,
                "type": "consu",
                "is_storable": True,
                "categ_id": categ.id,
                "uom_id": uom_unit.id,
                "uom_po_id": uom_unit.id,
                "list_price": price,
                "standard_price": round(price * 0.45, 2),
                "purchase_ok": False,
                "sale_ok": True,
            })
            variants[name] = template.product_variant_id
            Bom.create({
                "product_tmpl_id": template.id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": [
                    (0, 0, {"product_id": raw_variants[comp_name].id, "product_qty": qty})
                    for comp_name, qty in components
                ],
            })
            bom_count += 1
        return variants, bom_count

    def _get_or_create_category(self, name):
        Categ = self.env["product.category"]
        existing = Categ.search([("name", "=", name)], limit=1)
        return existing or Categ.create({"name": name})

    # ------------------------------------------------------------------
    # Stock
    # ------------------------------------------------------------------
    def _seed_raw_material_stock(self, raw_variants):
        location = self.env.ref("stock.stock_location_stock", raise_if_not_found=False)
        if not location:
            location = self.env["stock.location"].search([("usage", "=", "internal")], limit=1)
        Quant = self.env["stock.quant"].with_context(inventory_mode=True)
        for variant in raw_variants.values():
            quant = Quant.create({
                "product_id": variant.id,
                "location_id": location.id,
                "inventory_quantity": 500,
            })
            quant.action_apply_inventory()

    # ------------------------------------------------------------------
    # Purchase orders (vendor side)
    # ------------------------------------------------------------------
    def _create_purchase_orders(self, vendors, raw_variants):
        Purchase = self.env["purchase.order"]
        raw_list = list(raw_variants.values())
        stats = {"total": 0, "confirmed": 0}
        failed = 0
        for vendor in vendors:
            for _ in range(random.randint(2, 4)):
                lines = random.sample(raw_list, k=random.randint(1, 3))
                try:
                    order = Purchase.create({
                        "partner_id": vendor.id,
                        "order_line": [
                            (0, 0, {
                                "product_id": p.id,
                                "product_qty": random.randint(10, 100),
                                "product_uom": p.uom_po_id.id,
                                "price_unit": p.standard_price,
                                "date_planned": fields.Datetime.now() + timedelta(days=random.randint(1, 14)),
                            })
                            for p in lines
                        ],
                    })
                    stats["total"] += 1
                    if random.random() < 0.7:
                        order.button_confirm()
                        stats["confirmed"] += 1
                except Exception:
                    failed += 1
        return stats, failed

    # ------------------------------------------------------------------
    # Manufacturing orders
    # ------------------------------------------------------------------
    def _create_manufacturing_orders(self, finished_variants):
        Production = self.env["mrp.production"]
        Bom = self.env["mrp.bom"]
        stats = {"total": 0, "completed": 0, "confirmed_only": 0}
        failed = 0
        for name, variant in finished_variants.items():
            bom = Bom.search([("product_tmpl_id", "=", variant.product_tmpl_id.id)], limit=1)
            for _ in range(random.randint(2, 4)):
                try:
                    qty = random.randint(1, 5)
                    production = Production.create({
                        "product_id": variant.id,
                        "product_qty": qty,
                        "product_uom_id": variant.uom_id.id,
                        "bom_id": bom.id,
                    })
                    stats["total"] += 1
                    production.action_confirm()
                    if random.random() < 0.6:
                        production.qty_producing = qty
                        production.button_mark_done()
                        stats["completed"] += 1
                    else:
                        stats["confirmed_only"] += 1
                except Exception:
                    failed += 1
        return stats, failed

    # ------------------------------------------------------------------
    # Sales orders (customer side)
    # ------------------------------------------------------------------
    def _create_sales_orders(self, customers, finished_variants):
        Sale = self.env["sale.order"]
        finished_list = list(finished_variants.values())
        stats = {"total": 0, "confirmed": 0, "delivered": 0, "invoiced": 0}
        failed = 0
        for customer in customers:
            for _ in range(random.randint(1, 3)):
                lines = random.sample(finished_list, k=random.randint(1, 4))
                try:
                    order = Sale.create({
                        "partner_id": customer.id,
                        "order_line": [
                            (0, 0, {
                                "product_id": p.id,
                                "name": p.name,
                                "product_uom_qty": random.randint(1, 5),
                                "product_uom": p.uom_id.id,
                                "price_unit": p.list_price,
                            })
                            for p in lines
                        ],
                    })
                    stats["total"] += 1
                    if random.random() < 0.7:
                        order.action_confirm()
                        stats["confirmed"] += 1

                        if random.random() < 0.6:
                            for picking in order.picking_ids.filtered(lambda p: p.state not in ("done", "cancel")):
                                picking.button_validate()
                            stats["delivered"] += 1

                        if random.random() < 0.5:
                            invoice = order._create_invoices()
                            invoice.action_post()
                            stats["invoiced"] += 1
                except Exception:
                    failed += 1
        return stats, failed
