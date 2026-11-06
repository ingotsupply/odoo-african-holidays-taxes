# -*- coding: utf-8 -*-
"""Tests without network: the feed parser, the opt-in rule, and the import (create, then move an announced date)
with the feed request replaced by a fixed feed."""
import datetime
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from ..models import acd_client, res_company

FEED_V1 = """BEGIN:VCALENDAR\r
VERSION:2.0\r
BEGIN:VEVENT\r
UID:ke-%(y)s-new_year@africacompliancedata.com\r
DTSTART;VALUE=DATE:%(y)s0101\r
DTEND;VALUE=DATE:%(y)s0102\r
SUMMARY:New Year's Day\r
DESCRIPTION:Legal basis: https://example.org/act\\nMore: https://example.org/\r
STATUS:CONFIRMED\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:ke-%(y)s-eid_fitr@africacompliancedata.com\r
DTSTART;VALUE=DATE:%(y)s0320\r
DTEND;VALUE=DATE:%(y)s0321\r
SUMMARY:Idd-ul-Fitr\r
DESCRIPTION:Estimated\\, depends on the moon sighting.\r
STATUS:TENTATIVE\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:ke-%(old)s-new_year@africacompliancedata.com\r
DTSTART;VALUE=DATE:%(old)s0101\r
SUMMARY:Old year\r
END:VEVENT\r
END:VCALENDAR\r
"""


@tagged("post_install", "-at_install")
class TestAfricanHolidays(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.year = datetime.date.today().year
        cls.kenya = cls.env.ref("base.ke")
        # A company of its own: the test never depends on holidays already imported in the database.
        cls.company = cls.env["res.company"].create({"name": "ACD test company"})
        cls.company.write({"acd_country_ids": [(6, 0, cls.kenya.ids)], "acd_years_ahead": 0})

    def _feed(self, text):
        return patch.object(res_company, "fetch_holidays", lambda code: acd_client.parse_ics(text))

    def test_parse_ics(self):
        events = acd_client.parse_ics(FEED_V1 % {"y": 2026, "old": 2001})
        self.assertEqual(len(events), 3)
        eid = events[1]
        self.assertEqual(eid["start"], datetime.date(2026, 3, 20))
        self.assertEqual(eid["end"], datetime.date(2026, 3, 21))
        self.assertEqual(eid["status"], "TENTATIVE")
        self.assertEqual(eid["description"], "Estimated, depends on the moon sighting.")
        self.assertEqual(events[0]["description"], "Legal basis: https://example.org/act\nMore: https://example.org/")
        self.assertEqual(events[2]["end"], datetime.date(2001, 1, 2), "no DTEND: one day")

    def test_folded_lines(self):
        text = "BEGIN:VEVENT\r\nUID:x\r\nDTSTART;VALUE=DATE:20260101\r\nSUMMARY:Long \r\n name\r\nEND:VEVENT\r\n"
        self.assertEqual(acd_client.parse_ics(text)[0]["summary"], "Long name")

    def test_opt_in_required(self):
        self.env["ir.config_parameter"].sudo().set_param(res_company.PARAM_ENABLED, "False")
        with self._feed(FEED_V1 % {"y": self.year, "old": 2001}):
            with self.assertRaises(UserError):
                self.company.acd_sync_holidays()

    def test_import_then_move(self):
        self.env["ir.config_parameter"].sudo().set_param(res_company.PARAM_ENABLED, "True")
        Leaves = self.env["resource.calendar.leaves"]
        with self._feed(FEED_V1 % {"y": self.year, "old": 2001}):
            created, updated, errors = self.company.acd_sync_holidays()
        self.assertEqual((created, updated, errors), (2, 0, []), "only this year's holidays")
        eid = Leaves.search([("acd_uid", "=", "ke-%s-eid_fitr@africacompliancedata.com" % self.year),
                             ("company_id", "=", self.company.id)])
        self.assertEqual(len(eid), 1, "created in the company being synced, not the current one")
        self.assertEqual(eid.company_id, self.company)
        self.assertTrue(eid.acd_estimated)
        self.assertIn("(estimated)", eid.name)
        self.assertEqual(eid.acd_credit, "Africa Compliance Data")
        self.assertFalse(eid.resource_id)
        # Announced a day later and confirmed: the same entry moves, nothing is duplicated.
        moved = (FEED_V1 % {"y": self.year, "old": 2001}).replace(
            "%s0320" % self.year, "%s0321" % self.year).replace("%s0321\r\nSUMMARY:Idd" % self.year, "%s0322\r\nSUMMARY:Idd" % self.year)
        moved = moved.replace("STATUS:TENTATIVE", "STATUS:CONFIRMED")
        with self._feed(moved):
            created, updated, errors = self.company.acd_sync_holidays()
        self.assertEqual((created, updated), (0, 1))
        eid.invalidate_recordset()
        self.assertFalse(eid.acd_estimated)
        self.assertNotIn("(estimated)", eid.name)
        self.assertEqual(Leaves.search_count([("acd_uid", "like", "ke-%s-" % self.year), ("company_id", "=", self.company.id)]), 2)
        # Running again with the same feed changes nothing.
        with self._feed(moved):
            self.assertEqual(self.company.acd_sync_holidays()[:2], (0, 0))

    def test_unknown_country_feed(self):
        with self.assertRaises(acd_client.AcdError):
            acd_client.fetch_holidays("FR")
