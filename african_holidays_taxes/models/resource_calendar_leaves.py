# -*- coding: utf-8 -*-
from odoo import fields, models


class ResourceCalendarLeaves(models.Model):
    _inherit = "resource.calendar.leaves"

    acd_uid = fields.Char(string="Holiday feed ID", index=True, copy=False, readonly=True,
                          help="Identifier of the holiday in the Africa Compliance Data feed, used to update it.")
    acd_country_id = fields.Many2one("res.country", string="Holiday country", readonly=True)
    acd_estimated = fields.Boolean(string="Estimated date", readonly=True,
                                   help="The date depends on a moon sighting or an announcement and may change.")
    acd_source_note = fields.Text(string="Source", readonly=True)
    acd_credit = fields.Char(string="Data from", compute="_compute_acd_credit")

    def _compute_acd_credit(self):
        for leave in self:
            leave.acd_credit = "Africa Compliance Data" if leave.acd_uid else False
