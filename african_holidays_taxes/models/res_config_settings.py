# -*- coding: utf-8 -*-
from odoo import api, fields, models

from .res_company import PARAM_ENABLED

PARAM_KEY = "african_holidays_taxes.api_key"


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    acd_enabled = fields.Boolean(
        string="Connect to the Africa Compliance Data service", config_parameter=PARAM_ENABLED,
        help="Allows the requests described below. Nothing is sent while this is off.")
    acd_api_key = fields.Char(
        string="API key (optional)", config_parameter=PARAM_KEY,
        help="Your own Africa Compliance Data API key, only for the tax reference list. Holidays need no key.")
    acd_country_ids = fields.Many2many(related="company_id.acd_country_ids", readonly=False)
    acd_calendar_id = fields.Many2one(related="company_id.acd_calendar_id", readonly=False)
    acd_years_ahead = fields.Integer(related="company_id.acd_years_ahead", readonly=False)
    acd_weekly = fields.Boolean(string="Update every week", compute="_compute_acd_weekly", inverse="_inverse_acd_weekly")

    def _acd_cron(self):
        return self.env.ref("african_holidays_taxes.ir_cron_acd_sync", raise_if_not_found=False)

    @api.depends("company_id")
    def _compute_acd_weekly(self):
        cron = self._acd_cron()
        for rec in self:
            rec.acd_weekly = bool(cron and cron.sudo().active)

    def _inverse_acd_weekly(self):
        cron = self._acd_cron()
        if cron:
            for rec in self:
                cron.sudo().active = rec.acd_weekly

    def action_acd_sync_holidays(self):
        self.execute()   # save the settings first
        return self.company_id.action_acd_sync_holidays()

    def action_acd_update_tax_reference(self):
        self.execute()
        return self.env["acd.tax.reference"].action_update_for_company(self.company_id)
