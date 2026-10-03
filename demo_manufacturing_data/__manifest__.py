{
    "name": "Demo Manufacturing Company Seeder",
    "summary": "One-click realistic demo data: a furniture manufacturer with vendors, customers, products, BOMs, purchase/sales orders and manufacturing orders.",
    "description": """
Demo Manufacturing Company Seeder
==================================
A practice-environment tool, not a real business feature: one button that
populates the database with a believable small manufacturing company
("Nordica Hogar", a furniture maker) so there is real volume to click
through and break — vendors, customers, raw-material and finished-good
products with Bills of Materials, purchase orders, manufacturing orders,
and sales orders in a mix of draft/confirmed/delivered/invoiced states.

Settings ▸ Technical ▸ Demo Data ▸ Generate Manufacturing Company.

Running it again ADDS another batch rather than replacing the previous
one — reset the database (see repo README) for a clean slate instead.
""",
    "version": "19.0.1.0.0",
    "category": "Tools",
    "author": "Bogdan Starchenko",
    "license": "LGPL-3",
    "depends": ["base", "contacts", "product", "stock", "mrp", "sale_management", "purchase"],
    "data": [
        "security/ir.model.access.csv",
        "views/seeder_views.xml",
    ],
    "installable": True,
    "application": False,
}
