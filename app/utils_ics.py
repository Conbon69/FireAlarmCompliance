from __future__ import annotations

from datetime import datetime, timedelta, timezone, date
from uuid import uuid4


def _start_dt(start: date | None, hour: int = 9, minute: int = 0) -> datetime:
	if start is None:
		now = datetime.now(timezone.utc)
		# today
		base = datetime(year=now.year, month=now.month, day=now.day, tzinfo=timezone.utc)
		return base.replace(hour=hour, minute=minute, second=0, microsecond=0)
	return datetime(year=start.year, month=start.month, day=start.day, hour=hour, minute=minute, tzinfo=timezone.utc)


def _format_dt(dt: datetime) -> str:
	return dt.strftime("%Y%m%dT%H%M%SZ")


def build_monthly_ics(summary: str = "Test smoke and CO alarms",
					  description: str = "Monthly test reminder",
					  count: int = 12,
					  start_date: date | None = None) -> str:
	"""Return an ICS file content with one VEVENT and a monthly RRULE for `count` months starting at `start_date` or today."""
	uid = f"{uuid4()}@fire-alarm-compliance"
	start = _start_dt(start_date)
	created = datetime.now(timezone.utc)

	lines = [
		"BEGIN:VCALENDAR",
		"VERSION:2.0",
		"PRODID:-//Fire Alarm Compliance//MVP//EN",
		"CALSCALE:GREGORIAN",
		"METHOD:PUBLISH",
		"BEGIN:VEVENT",
		f"UID:{uid}",
		f"DTSTAMP:{_format_dt(created)}",
		f"DTSTART:{_format_dt(start)}",
		f"SUMMARY:{summary}",
		f"DESCRIPTION:{description}",
		f"RRULE:FREQ=MONTHLY;COUNT={count}",
		"END:VEVENT",
		"END:VCALENDAR",
	]
	return "\r\n".join(lines) + "\r\n"


