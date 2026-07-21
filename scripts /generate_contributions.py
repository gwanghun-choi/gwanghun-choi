from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape


GITHUB_API = "https://api.github.com/graphql"

USERNAME = os.environ["GH_USERNAME"]
TOKEN = os.environ["GH_TOKEN"]

OUTPUT_PATH = Path("assets/github-contributions-90d.svg")

DAYS = 90

BACKGROUND = "#0F172A"
CARD_BACKGROUND = "#111827"
BORDER = "#334155"

TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#94A3B8"
ACCENT = "#2563EB"

LEVEL_COLORS = {
    0: "#1E293B",
    1: "#1E3A8A",
    2: "#1D4ED8",
    3: "#2563EB",
    4: "#60A5FA",
}


def graphql_request(query: str, variables: dict) -> dict:
    payload = json.dumps(
        {
            "query": query,
            "variables": variables,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        GITHUB_API,
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "github-profile-contribution-generator",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)

    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"], ensure_ascii=False))

    return result["data"]


def contribution_level_to_int(level: str) -> int:
    levels = {
        "NONE": 0,
        "FIRST_QUARTILE": 1,
        "SECOND_QUARTILE": 2,
        "THIRD_QUARTILE": 3,
        "FOURTH_QUARTILE": 4,
    }
    return levels.get(level, 0)


def build_svg(days: list[dict], total: int, private_total: int) -> str:
    cell = 14
    gap = 4
    grid_x = 72
    grid_y = 100

    columns = 14
    rows = 7

    width = 940
    height = 330

    first_date = datetime.fromisoformat(days[0]["date"])
    last_date = datetime.fromisoformat(days[-1]["date"])

    private_text = (
        f"{private_total} contributions in private repositories"
        if private_total > 0
        else "No private contributions in this period"
    )

    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        "<style>",
        "text { font-family: -apple-system, BlinkMacSystemFont, "
        "'Segoe UI', Helvetica, Arial, sans-serif; }",
        "</style>",
        f'<rect width="{width}" height="{height}" rx="14" fill="{BACKGROUND}"/>',
        (
            f'<rect x="1" y="1" width="{width - 2}" height="{height - 2}" '
            f'rx="14" fill="none" stroke="{BORDER}"/>'
        ),
        (
            f'<text x="28" y="42" fill="{TEXT_PRIMARY}" '
            f'font-size="20" font-weight="600">'
            f'{total} contributions in the last 3 months</text>'
        ),
    ]

    month_positions: dict[str, int] = {}

    for index, day in enumerate(days):
        date = datetime.fromisoformat(day["date"])
        week_index = index // 7
        weekday = date.weekday()

        # Python: Mon=0, GitHub 스타일: Sun=0
        row = (weekday + 1) % 7

        x = grid_x + week_index * (cell + gap)
        y = grid_y + row * (cell + gap)

        month_key = date.strftime("%Y-%m")
        month_positions.setdefault(month_key, x)

        level = contribution_level_to_int(day["contributionLevel"])
        count = day["contributionCount"]
        color = LEVEL_COLORS[level]

        tooltip = escape(f'{day["date"]}: {count} contributions')

        svg.extend(
            [
                f"<title>{tooltip}</title>",
                (
                    f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                    f'rx="3" fill="{color}"/>'
                ),
            ]
        )

    for month_key, x in month_positions.items():
        label = datetime.strptime(month_key, "%Y-%m").strftime("%b")

        svg.append(
            f'<text x="{x}" y="83" fill="{TEXT_SECONDARY}" '
            f'font-size="13">{label}</text>'
        )

    weekday_labels = {
        1: "Mon",
        3: "Wed",
        5: "Fri",
    }

    for row, label in weekday_labels.items():
        y = grid_y + row * (cell + gap) + 12

        svg.append(
            f'<text x="28" y="{y}" fill="{TEXT_SECONDARY}" '
            f'font-size="12">{label}</text>'
        )

    legend_x = 680
    legend_y = 236

    svg.append(
        f'<text x="{legend_x}" y="{legend_y}" '
        f'fill="{TEXT_SECONDARY}" font-size="12">Less</text>'
    )

    for level in range(5):
        x = legend_x + 38 + level * 20
        svg.append(
            f'<rect x="{x}" y="{legend_y - 12}" width="14" height="14" '
            f'rx="3" fill="{LEVEL_COLORS[level]}"/>'
        )

    svg.append(
        f'<text x="{legend_x + 145}" y="{legend_y}" '
        f'fill="{TEXT_SECONDARY}" font-size="12">More</text>'
    )

    svg.extend(
        [
            (
                f'<line x1="28" y1="260" x2="{width - 28}" y2="260" '
                f'stroke="{BORDER}"/>'
            ),
            f'<text x="34" y="296" fill="{ACCENT}" font-size="17">🔒</text>',
            (
                f'<text x="68" y="296" fill="{TEXT_SECONDARY}" '
                f'font-size="16">{escape(private_text)}</text>'
            ),
            (
                f'<text x="{width - 28}" y="296" fill="{TEXT_SECONDARY}" '
                f'font-size="13" text-anchor="end">'
                f'{first_date.strftime("%b %-d")} – '
                f'{last_date.strftime("%b %-d, %Y")}</text>'
            ),
            "</svg>",
        ]
    )

    return "\n".join(svg)


def main() -> None:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=DAYS - 1)

    query = """
    query UserContributions(
      $login: String!,
      $from: DateTime!,
      $to: DateTime!
    ) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
                contributionLevel
              }
            }
          }
          restrictedContributionsCount
        }
      }
    }
    """

    data = graphql_request(
        query,
        {
            "login": USERNAME,
            "from": start.isoformat(),
            "to": now.isoformat(),
        },
    )

    collection = data["user"]["contributionsCollection"]
    calendar = collection["contributionCalendar"]

    days = [
        day
        for week in calendar["weeks"]
        for day in week["contributionDays"]
        if start.date().isoformat() <= day["date"] <= now.date().isoformat()
    ]

    days.sort(key=lambda item: item["date"])

    svg = build_svg(
        days=days,
        total=calendar["totalContributions"],
        private_total=collection["restrictedContributionsCount"],
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    main()
