# African Holidays & Taxes (Odoo 19)

Imports the national public holidays of the 54 African countries into Odoo's public holidays (working schedules and
Time Off), with moon-sighted holidays marked as estimated until announced, and an optional read-only reference list of
VAT, withholding tax and e-invoicing data.

- **External service:** Africa Compliance Data. Nothing is sent until an administrator turns the connection on in
  Settings. Holiday requests contain only the country code (public feeds, no account needed, free for business use
  with credit). Tax reference requests contain only the country code and the customer's own API key. No business data
  is ever sent.
- **Install:** copy `african_holidays_taxes` into an addons path; depends only on `base` and `resource`.
- **Use:** Settings, African Holidays & Taxes: turn on the connection, choose countries, click Import public holidays.
- **Tests:** `odoo -d <db> -i african_holidays_taxes --test-enable --test-tags /african_holidays_taxes --stop-after-init`
  (no network needed: the feed is replaced by a fixed one).
- **Licence:** LGPL-3 (see LICENSE). Support: support@africacompliancedata.com
