import asyncio
import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.async_api import async_playwright

CIAC_URL = "https://ciac.fpsports.org/DashboardTeamSchedule.aspx?SportGenderListID=7&Status=0&SchoolID=159&TeamLevelID=1"
OUTPUT = Path("docs/calendar.ics")
TZ = ZoneInfo("America/New_York")

def esc(s: str) -> str:
    s = (s or "").replace("\\", "\\\\").replace("\n", "\\n")
    return s.replace(",", "\\,").replace(";", "\\;")

def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip())

def parse_date_time(date_text, time_text):
    # CIAC typically displays dates like TUE 9/8 and times like 4:00 PM.
    md = re.search(r"(\d{1,2})/(\d{1,2})", date_text)
    if not md:
        return None
    month, day = map(int, md.groups())

    # Infer year from current date. If month is far behind current month,
    # assume the next calendar year.
    now = datetime.now(TZ)
    year = now.year
    if month < now.month - 6:
        year += 1
    elif month > now.month + 6:
        year -= 1

    tm = datetime.strptime(norm(time_text), "%I:%M %p").time()
    return datetime(year, month, day, tm.hour, tm.minute, tzinfo=TZ)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={"width": 1600, "height": 1200},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
        )
        await page.goto(CIAC_URL, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(5000)

        # Find a table containing the schedule headers.
        tables = page.locator("table")
        count = await tables.count()
        schedule_table = None
        for i in range(count):
            txt = norm(await tables.nth(i).inner_text())
            if all(x in txt for x in ["Date", "Time", "Opponent", "Site"]):
                schedule_table = tables.nth(i)
                break

        if schedule_table is None:
            # Save the HTML to make debugging easy if CIAC changes its site.
            Path("ciac_debug.html").write_text(await page.content(), encoding="utf-8")
            raise RuntimeError("Could not locate the CIAC Team Schedule table.")

        rows = schedule_table.locator("tr")
        n = await rows.count()
        parsed = []

        for i in range(n):
            cells = rows.nth(i).locator("th,td")
            c = await cells.count()
            if c < 8:
                continue

            vals = [norm(await cells.nth(j).inner_text()) for j in range(c)]
            # Skip header rows.
            if vals and vals[0].lower() == "date":
                continue

            # Expected order visible on CIAC:
            # Date, Time, Team Level, Type, Status, Time, Home/Away,
            # Opponent, Result, Score, Details, Site, Transportation
            date_text = vals[0] if c > 0 else ""
            game_time = vals[1] if c > 1 else ""
            team_level = vals[2] if c > 2 else ""
            game_type = vals[3] if c > 3 else ""
            status = vals[4] if c > 4 else ""
            home_away = vals[6] if c > 6 else ""
            opponent = vals[7] if c > 7 else ""
            details = vals[10] if c > 10 else ""
            site = vals[11] if c > 11 else ""
            transportation = vals[12] if c > 12 else ""

            if not date_text or not game_time or not opponent:
                continue

            try:
                start = parse_date_time(date_text, game_time)
            except Exception:
                continue
            if not start:
                continue

            # Soccer games are represented as 2-hour calendar blocks.
            end = start + timedelta(hours=2)

            parsed.append({
                "start": start,
                "end": end,
                "team_level": team_level,
                "type": game_type,
                "status": status,
                "home_away": home_away,
                "opponent": opponent,
                "details": details,
                "site": site,
                "transportation": transportation,
            })

        await browser.close()

    if not parsed:
        raise RuntimeError("Schedule table was found but no games could be parsed.")

    stamp = datetime.now(TZ).astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CIAC Live Calendar//Trumbull Boys Soccer//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Trumbull Boys Soccer - Freshman",
        "X-WR-TIMEZONE:America/New_York",
        "X-PUBLISHED-TTL:PT4H",
        "REFRESH-INTERVAL;VALUE=DURATION:PT4H",
    ]

    for g in sorted(parsed, key=lambda x: x["start"]):
        raw_uid = f'{g["start"].isoformat()}|{g["opponent"]}|{g["site"]}'
        uid = hashlib.sha1(raw_uid.encode()).hexdigest() + "@ciac-live-calendar"

        title = f'Trumbull Boys Soccer vs {g["opponent"]}'
        if g["home_away"]:
            title += f' ({g["home_away"]})'

        desc_parts = []
        if g["team_level"]:
            desc_parts.append(f'Team: {g["team_level"]}')
        if g["type"]:
            desc_parts.append(f'Type: {g["type"]}')
        if g["status"]:
            desc_parts.append(f'Status: {g["status"]}')
        if g["transportation"]:
            desc_parts.append(f'Transportation: {g["transportation"]}')
        if g["details"]:
            desc_parts.append(f'Details: {g["details"]}')
        desc_parts.append(f'CIAC schedule: {CIAC_URL}')

        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp}",
            f'DTSTART;TZID=America/New_York:{g["start"].strftime("%Y%m%dT%H%M%S")}',
            f'DTEND;TZID=America/New_York:{g["end"].strftime("%Y%m%dT%H%M%S")}',
            f"SUMMARY:{esc(title)}",
            f"LOCATION:{esc(g['site'])}",
            f"DESCRIPTION:{esc(chr(10).join(desc_parts))}",
            f"URL:{CIAC_URL}",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    print(f"Wrote {len(parsed)} games to {OUTPUT}")

if __name__ == "__main__":
    asyncio.run(main())
