# -*- coding: utf-8 -*-
"""Client for the Africa Compliance Data service: the public holiday feeds (no key) and, with the customer's own API
key, the tax reference endpoints. Only the country code (and the key, for the API) is ever sent."""
import datetime
import logging

import requests

_logger = logging.getLogger(__name__)

FEED_URL = "https://africacompliancedata.com/calendar/%s.ics"
API_URL = "https://api.africacompliancedata.com/v1/countries/%s/%s"
USER_AGENT = "Odoo-african_holidays_taxes/19.0.1.0.0"
TIMEOUT = 20

# The 54 African countries the service covers (ISO 3166-1 alpha-2).
AFRICA = {
    "DZ", "AO", "BJ", "BW", "BF", "BI", "CV", "CM", "CF", "TD", "KM", "CG", "CD", "CI", "DJ", "EG", "GQ", "ER", "SZ",
    "ET", "GA", "GM", "GH", "GN", "GW", "KE", "LS", "LR", "LY", "MG", "MW", "ML", "MR", "MU", "MA", "MZ", "NA", "NE",
    "NG", "RW", "ST", "SN", "SC", "SL", "SO", "ZA", "SS", "SD", "TZ", "TG", "TN", "UG", "ZM", "ZW",
}


class AcdError(Exception):
    """A readable error for the user (network failure, refusal by the service)."""


def _unescape(value):
    return (value.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",")
            .replace("\\;", ";").replace("\\\\", "\\"))


def parse_ics(text):
    """Events of an iCalendar text: [{uid, summary, start (date), end (date, exclusive), status, description}].
    Only what the holiday feeds use: all-day VEVENTs with UID, SUMMARY, DTSTART/DTEND;VALUE=DATE and STATUS."""
    lines = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]          # folded line (RFC 5545 3.1)
        elif raw:
            lines.append(raw)
    events, cur = [], None
    for line in lines:
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT":
            if cur and cur.get("uid") and cur.get("start"):
                cur.setdefault("end", cur["start"] + datetime.timedelta(days=1))
                cur.setdefault("status", "CONFIRMED")
                cur.setdefault("summary", "")
                cur.setdefault("description", "")
                events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            name, value = line.split(":", 1)
            key = name.split(";", 1)[0].upper()
            if key == "UID":
                cur["uid"] = value.strip()
            elif key == "SUMMARY":
                cur["summary"] = _unescape(value).strip()
            elif key == "DESCRIPTION":
                cur["description"] = _unescape(value).strip()
            elif key == "STATUS":
                cur["status"] = value.strip().upper()
            elif key in ("DTSTART", "DTEND"):
                v = value.strip()[:8]
                try:
                    day = datetime.date(int(v[:4]), int(v[4:6]), int(v[6:8]))
                except ValueError:
                    continue
                cur["start" if key == "DTSTART" else "end"] = day
    return events


def fetch_holidays(country_code):
    """Events of a country's public holiday feed (no key)."""
    code = (country_code or "").upper()
    if code not in AFRICA:
        raise AcdError("No holiday feed for country %s (only the 54 African countries are covered)." % code)
    try:
        resp = requests.get(FEED_URL % code.lower(), timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
    except requests.RequestException as exc:
        raise AcdError("Could not reach the holiday feed for %s: %s" % (code, exc)) from exc
    if resp.status_code != 200:
        raise AcdError("The holiday feed for %s answered HTTP %s." % (code, resp.status_code))
    return parse_ics(resp.content.decode("utf-8", "replace"))


def api_get(country_code, path, api_key, base_url=None):
    """JSON answer of a tax endpoint, with the customer's own API key. Refusals are raised with the service's message.
    base_url: only to test against another server (system parameter african_holidays_taxes.api_url)."""
    code = (country_code or "").upper()
    url = (base_url.rstrip("/") + "/v1/countries/%s/%s") if base_url else API_URL
    try:
        resp = requests.get(url % (code, path), timeout=TIMEOUT,
                            headers={"x-api-key": api_key, "User-Agent": USER_AGENT, "Accept": "application/json"})
    except requests.RequestException as exc:
        raise AcdError("Could not reach the service for %s: %s" % (code, exc)) from exc
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.status_code != 200:
        raise AcdError("%s (%s): %s" % (code, path, body.get("error") or "HTTP %s" % resp.status_code))
    return body
