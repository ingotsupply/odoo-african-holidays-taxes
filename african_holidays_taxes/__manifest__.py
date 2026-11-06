# -*- coding: utf-8 -*-
{
    "name": "African Holidays & Taxes",
    "version": "19.0.1.0.0",
    "support": "support@africacompliancedata.com",
    "summary": "Public holidays of 54 African countries in your working calendars, with an optional tax reference list",
    "description": """
Imports the national public holidays of the African countries you choose into Odoo's public holidays (working
calendars and Time Off), including moon-sighted holidays marked as estimated until the date is announced. Runs again
on demand or weekly to pick up announced dates.

External service: this module uses the Africa Compliance Data service. Nothing is sent until an administrator turns
the connection on in Settings. Holidays come from its public calendar feeds (no account needed); the request contains
only the country code. An optional API key adds a read-only reference list of VAT, withholding tax and e-invoicing
data for the chosen countries; those requests contain only the country code and the key. No partner, invoice,
employee or other business data is ever sent.
""",
    "category": "Human Resources/Time Off",
    "author": "Ingot Supply, LLC",
    "license": "LGPL-3",
    "depends": ["base", "resource"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/resource_calendar_leaves_views.xml",
        "views/acd_tax_reference_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
}
