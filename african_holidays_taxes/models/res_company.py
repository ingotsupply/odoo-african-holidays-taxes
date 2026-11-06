# -*- coding: utf-8 -*-
import datetime
import logging

import pytz

from odoo import _, fields, models
from odoo.exceptions import UserError

from .acd_client import AFRICA, AcdError, fetch_holidays

_logger = logging.getLogger(__name__)

PARAM_ENABLED = "african_holidays_taxes.enabled"


class ResCompany(models.Model):
    _inherit = "res.company"

    acd_country_ids = fields.Many2many(
        "res.country", "acd_company_country_rel", "company_id", "country_id", string="African countries",
        domain=[("code", "in", sorted(AFRICA))],
        help="Countries whose national public holidays (and, with an API key, tax reference data) are imported.")
    acd_calendar_id = fields.Many2one(
        "resource.calendar", string="Working schedule",
        help="Working schedule the public holidays apply to. Leave empty to apply them to all working schedules of "
             "the company.")
    acd_years_ahead = fields.Integer(
        string="Years ahead", default=1,
        help="Import the current year and this many following years (0 to 3).")

    # ---------- public holidays ----------
    def _acd_check_enabled(self):
        if self.env["ir.config_parameter"].sudo().get_param(PARAM_ENABLED) != "True":
            raise UserError(_("The connection to the Africa Compliance Data service is turned off. Turn it on in "
                              "Settings (African Holidays & Taxes) to allow the requests described there."))

    def _acd_bounds(self, event, tz):
        """UTC naive start and end of an all-day holiday in the schedule's time zone (Odoo stores UTC)."""
        start = tz.localize(datetime.datetime.combine(event["start"], datetime.time.min))
        last_day = event["end"] - datetime.timedelta(days=1)
        end = tz.localize(datetime.datetime.combine(last_day, datetime.time(23, 59, 59)))
        return (start.astimezone(pytz.utc).replace(tzinfo=None), end.astimezone(pytz.utc).replace(tzinfo=None))

    def acd_sync_holidays(self):
        """Creates or updates the public holidays of the selected countries for the current year and the years
        ahead. A holiday is matched on its feed UID: an announced date moves the existing entry. Entries are never
        deleted. Returns (created, updated, errors)."""
        self._acd_check_enabled()
        Leaves = self.env["resource.calendar.leaves"].sudo()
        created = updated = 0
        errors = []
        today = fields.Date.context_today(self)
        for company in self:
            years = set(range(today.year, today.year + max(0, min(company.acd_years_ahead, 3)) + 1))
            calendar = company.acd_calendar_id
            tz = pytz.timezone((calendar or company.resource_calendar_id).tz or "UTC")
            for country in company.acd_country_ids:
                try:
                    events = fetch_holidays(country.code)
                except AcdError as exc:
                    errors.append(str(exc))
                    continue
                for ev in events:
                    if ev["start"].year not in years:
                        continue
                    date_from, date_to = self._acd_bounds(ev, tz)
                    estimated = ev["status"] == "TENTATIVE"
                    name = ev["summary"] + (_(" (estimated)") if estimated else "")
                    vals = {
                        "name": "%s: %s" % (country.code, name),
                        "date_from": date_from,
                        "date_to": date_to,
                        "calendar_id": calendar.id or False,
                        "resource_id": False,
                        "time_type": "leave",
                        "acd_uid": ev["uid"],
                        "acd_country_id": country.id,
                        "acd_estimated": estimated,
                        "acd_source_note": ev["description"],
                    }
                    # Odoo computes a public holiday's company from its schedule, or else from the current company:
                    # create it within the company it belongs to (multi-company databases).
                    company_leaves = Leaves.with_company(company)
                    existing = company_leaves.search([("acd_uid", "=", ev["uid"]), ("company_id", "=", company.id)], limit=1)
                    if existing:
                        # An announced date, a new name or a confirmed status: update; otherwise leave it untouched.
                        if (existing.date_from, existing.date_to, existing.name, existing.acd_estimated) != \
                                (date_from, date_to, vals["name"], estimated):
                            existing.write({k: vals[k] for k in ("name", "date_from", "date_to", "acd_estimated",
                                                                  "acd_source_note")})
                            updated += 1
                    else:
                        # Flush at once: the stored company is computed lazily, and must be computed in this
                        # company's context, not in whatever context flushes later.
                        company_leaves.create(vals).flush_recordset()
                        created += 1
        return created, updated, errors

    def action_acd_sync_holidays(self):
        created, updated, errors = self.acd_sync_holidays()
        message = _("%(c)s public holidays added, %(u)s updated.", c=created, u=updated)
        if errors:
            message += "\n" + "\n".join(errors)
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": _("African public holidays"), "message": message,
                           "type": "warning" if errors else "success", "sticky": bool(errors)}}

    def _cron_acd_sync(self):
        """Weekly update (the scheduled action is off until the administrator turns it on)."""
        if self.env["ir.config_parameter"].sudo().get_param(PARAM_ENABLED) != "True":
            return
        companies = self.search([("acd_country_ids", "!=", False)])
        if companies:
            _created, _updated, errors = companies.acd_sync_holidays()
            for err in errors:
                _logger.warning("African Holidays & Taxes: %s", err)
