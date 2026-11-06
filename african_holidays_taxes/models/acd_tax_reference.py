# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError

from .acd_client import AcdError, api_get as _api_get
from .res_company import PARAM_ENABLED
from .res_config_settings import PARAM_KEY

PAYMENT_TYPES = {
    "dividends": "Dividends", "interest": "Interest", "royalties": "Royalties", "rent": "Rent", "services": "Services",
    "professional_fees": "Professional fees", "management_fees": "Management fees", "technical_fees": "Technical fees",
    "contracts": "Contracts", "goods": "Goods", "commissions": "Commissions", "directors_fees": "Directors' fees",
    "other": "Other",
}


class AcdTaxReference(models.Model):
    """Read-only reference list of VAT, withholding tax and e-invoicing data from the Africa Compliance Data API.
    It does not change the company's taxes: the accountant decides what to set up."""
    _name = "acd.tax.reference"
    _description = "African tax reference"
    _order = "country_id, kind, label"

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, readonly=True)
    country_id = fields.Many2one("res.country", required=True, readonly=True)
    kind = fields.Selection([("vat", "VAT"), ("wht", "Withholding tax"), ("einvoicing", "E-invoicing")],
                            required=True, readonly=True)
    label = fields.Char(required=True, readonly=True)
    # Rates are never summed in grouped lists (aggregator=None).
    rate = fields.Float(string="Rate (%)", readonly=True, aggregator=None)
    resident_rate = fields.Float(string="Resident rate (%)", readonly=True, aggregator=None)
    non_resident_rate = fields.Float(string="Non-resident rate (%)", readonly=True, aggregator=None)
    has_rate = fields.Boolean(readonly=True)
    detail = fields.Text(readonly=True)
    legal_basis = fields.Char(readonly=True)
    source_url = fields.Char(string="Source", readonly=True)
    confidence = fields.Char(readonly=True)
    fetched_on = fields.Datetime(readonly=True)

    def _rows_for(self, code, key):
        rows = []
        base = self.env["ir.config_parameter"].sudo().get_param("african_holidays_taxes.api_url") or None

        def api_get(c, path, k):
            return _api_get(c, path, k, base)

        vat = api_get(code, "vat", key)
        v = vat.get("vat") or {}
        src = next(iter((vat.get("sources") or {}).values()), {})
        if v.get("standard_rate") is not None:
            rows.append({"kind": "vat", "label": _("%s standard rate", v.get("name") or "VAT"), "rate": v["standard_rate"],
                         "has_rate": True, "detail": v.get("notes") or "", "legal_basis": src.get("legal_basis"),
                         "source_url": src.get("url"), "confidence": src.get("confidence")})
        for other in v.get("other_rates") or []:
            if isinstance(other.get("rate"), (int, float)):
                rows.append({"kind": "vat", "label": other.get("applies_to") or _("Other rate"), "rate": other["rate"],
                             "has_rate": True, "legal_basis": src.get("legal_basis"), "source_url": src.get("url"),
                             "confidence": src.get("confidence")})
        wht = api_get(code, "withholding-tax", key)
        wsrc = next(iter((wht.get("sources") or {}).values()), {})
        for item in (wht.get("withholding_tax") or {}).get("items") or []:
            res, non = item.get("resident_rate"), item.get("non_resident_rate")
            label = PAYMENT_TYPES.get(item.get("payment_type"), item.get("payment_type"))
            if item.get("payment_type") == "other" and item.get("notes"):
                # Several "other" items per country: name each by the start of its own description.
                first = item["notes"].split(":")[0].split(".")[0].strip()
                label = "%s: %s" % (label, first[:60])
            rows.append({"kind": "wht", "label": label,
                         "resident_rate": res or 0.0, "non_resident_rate": non or 0.0, "has_rate": res is not None or non is not None,
                         "detail": "\n".join(x for x in [
                             _("Resident rate not given") if res is None else "",
                             _("Non-resident rate not given") if non is None else "",
                             item.get("notes") or ""] if x),
                         "legal_basis": wsrc.get("legal_basis"), "source_url": wsrc.get("url"), "confidence": wsrc.get("confidence")})
        einv = (api_get(code, "e-invoicing", key).get("einvoicing")) or {}
        if einv:
            status = einv.get("status", "")
            first = einv.get("first_phase_from") or ""
            rows.append({"kind": "einvoicing", "label": einv.get("system_name") or _("No requirement found"),
                         "has_rate": False,
                         "detail": "\n".join(x for x in [_("Status: %s", status), _("Applies from: %s", first) if first else "",
                                                         einv.get("notes") or "", einv.get("where_looked") or ""] if x),
                         "legal_basis": einv.get("legal_basis"), "source_url": einv.get("source_url"),
                         "confidence": einv.get("confidence")})
        return rows

    def action_update_for_company(self, company):
        if isinstance(company, int):
            company = self.env["res.company"].browse(company)
        params = self.env["ir.config_parameter"].sudo()
        if params.get_param(PARAM_ENABLED) != "True":
            raise UserError(_("The connection to the Africa Compliance Data service is turned off. Turn it on in Settings first."))
        key = (params.get_param(PARAM_KEY) or "").strip()
        if not key:
            raise UserError(_("The tax reference list needs your Africa Compliance Data API key (Settings). "
                              "Public holidays need no key."))
        if not company.acd_country_ids:
            raise UserError(_("Choose at least one African country in Settings."))
        now = fields.Datetime.now()
        done, errors = 0, []
        for country in company.acd_country_ids:
            try:
                rows = self._rows_for(country.code, key)
            except AcdError as exc:
                errors.append(str(exc))
                continue
            self.sudo().search([("company_id", "=", company.id), ("country_id", "=", country.id)]).unlink()
            self.sudo().create([dict(r, company_id=company.id, country_id=country.id, fetched_on=now) for r in rows])
            done += 1
        message = _("Tax reference updated for %s countries.", done)
        if errors:
            message += "\n" + "\n".join(errors)
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": _("African tax reference"), "message": message,
                           "type": "warning" if errors else "success", "sticky": bool(errors)}}
