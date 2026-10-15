"""Read-only CalDAV window. Recurrence expansion is performed by the calendar server."""
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from xml.etree import ElementTree as ET
from .adapters import item, result
from .transport import ProviderError


def calendar_date(key, value):
    if "VALUE=DATE" in key or re.fullmatch(r"\d{8}", value):
        return datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc), True
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc), False
    match = re.search(r'(?:^|;)TZID="?([^";]+)', key)
    if not match:
        raise ProviderError("De agenda geeft een tijdstip zonder tijdzone terug.")
    return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=ZoneInfo(match[1])).astimezone(timezone.utc), False


def parse_calendar(xml, start, end):
    if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
        raise ProviderError("Ongeldige agenda-XML.")
    root = ET.fromstring(xml)
    if root.tag != "{DAV:}multistatus":
        raise ProviderError("Ongeldig agenda-antwoord.")
    events = []
    for response in root.findall("{DAV:}response"):
        for propstat in response.findall("{DAV:}propstat"):
            status = propstat.findtext("{DAV:}status", "")
            if " 200 " not in status:
                raise ProviderError("De agenda kon niet volledig worden gelezen.")
            for calendar in propstat.findall(".//{urn:ietf:params:xml:ns:caldav}calendar-data"):
                lines = re.sub(r"\r?\n[ \t]", "", calendar.text or "").splitlines()
                event, depth = None, 0
                for line in lines:
                    if line == "BEGIN:VEVENT":
                        event, depth = {}, 0
                    elif event is not None and line == "END:VEVENT":
                        if "RRULE" in event:
                            raise ProviderError("De agenda heeft terugkerende afspraken niet uitgewerkt.")
                        if event.get("STATUS", ("", ""))[1] != "CANCELLED":
                            key, value = event["DTSTART"]
                            begin, all_day = calendar_date(key, value)
                            if "DURATION" in event and "DTEND" in event:
                                raise ProviderError("Dubbele duur van afspraak.")
                            duration = timedelta(days=1) if all_day else timedelta(seconds=1)
                            if "DURATION" in event:
                                match = re.fullmatch(r"P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", event["DURATION"][1])
                                if not match or not any(match.groups()):
                                    raise ProviderError("Ongeldige duur van afspraak.")
                                duration = timedelta(**dict(zip(("weeks", "days", "hours", "minutes", "seconds"), (int(v or 0) for v in match.groups()))))
                            finish = calendar_date(*event["DTEND"])[0] if "DTEND" in event else begin + duration
                            if finish <= begin:
                                raise ProviderError("Ongeldige duur van afspraak.")
                            if begin < end and finish > start:
                                title = event.get("SUMMARY", ("", "Afspraak"))[1]
                                title = re.sub(r"\\([nN,;\\])", lambda m: "\n" if m[1] in "nN" else m[1], title)
                                values = item(str(len(events)), title, "Hele dag" if all_day else "", date=begin.date().isoformat() if all_day else begin.isoformat())
                                values["allDay"] = all_day
                                events.append(values)
                                if len(events) > 1000:
                                    raise ProviderError("Te veel afspraken in deze periode.")
                        event = None
                    elif event is not None:
                        if line.startswith("BEGIN:"):
                            depth += 1
                        elif line.startswith("END:"):
                            depth -= 1
                        elif depth == 0 and ":" in line:
                            key, value = line.split(":", 1)
                            name = key.split(";", 1)[0]
                            if name in ("DTSTART", "DTEND", "DURATION", "RRULE", "SUMMARY", "STATUS"):
                                if name in event:
                                    raise ProviderError("Dubbel agendaveld.")
                                event[name] = (key, value)
                if event is not None:
                    raise ProviderError("Onvolledige agenda-afspraak.")
    return result(sorted(events, key=lambda event: event["date"]))


def nextcloud(t, s):
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    first, last = (d.strftime("%Y%m%dT%H%M%SZ") for d in (start, end))
    body = f'''<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:prop><c:calendar-data><c:expand start="{first}" end="{last}"/></c:calendar-data></d:prop><c:filter><c:comp-filter name="VCALENDAR"><c:comp-filter name="VEVENT"><c:time-range start="{first}" end="{last}"/></c:comp-filter></c:comp-filter></c:filter></c:calendar-query>'''
    xml = t.call(method="REPORT", data=body.encode(), raw=True, headers={"Depth": "1", "Content-Type": "application/xml; charset=utf-8"}, auth=(s["username"], s["password"]))
    return parse_calendar(xml, start, end)
