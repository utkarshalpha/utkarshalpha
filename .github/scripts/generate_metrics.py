#!/usr/bin/env python3
"""Generate the auto-updating metrics card (metrics-light.svg /
metrics-dark.svg) embedded in the profile README.

Data sources: the GitHub search API for upstream PRs (authored by USER,
outside USER's own repos) and GraphQL for the past-year contribution
count. Run on a schedule by .github/workflows/metrics.yml; safe to run
locally (without GITHUB_TOKEN the contributions stat is omitted).
"""

import datetime as dt
import html
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

USER = "utkarshalpha"
ROOT = Path(__file__).resolve().parents[2]
NOW = dt.datetime.now(dt.timezone.utc)

W, H = 820, 240

LIGHT = {"bg": "#ffffff", "border": "#d0d7de", "text": "#24292f",
         "dim": "#57606a", "accent": "#8250df"}
DARK = {"bg": "#0d1117", "border": "#30363d", "text": "#e6edf3",
        "dim": "#8b949e", "accent": "#a371f7"}


def _request(url, payload=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload else None,
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": USER})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def search_prs(extra):
    q = urllib.parse.quote_plus(f"type:pr author:{USER} -user:{USER} {extra}")
    return _request("https://api.github.com/search/issues"
                    f"?q={q}&sort=updated&order=desc&per_page=30")


def contributions():
    """Past-year contribution count via GraphQL (token required)."""
    if not os.environ.get("GITHUB_TOKEN"):
        return None
    query = ('query { user(login: "%s") { contributionsCollection '
             '{ contributionCalendar { totalContributions } } } }' % USER)
    try:
        data = _request("https://api.github.com/graphql", {"query": query})
        return (data["data"]["user"]["contributionsCollection"]
                ["contributionCalendar"]["totalContributions"])
    except Exception:
        return None


def rel_time(iso):
    then = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    days = (NOW - then).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    if days < 60:
        return f"{days // 7} weeks ago"
    if days < 730:
        return f"{days // 30} months ago"
    return f"{days // 365} years ago"


def _repo(item):
    return item["repository_url"].split("/repos/")[1]


def _merged_at(item):
    return item["pull_request"].get("merged_at") or item["closed_at"]


def gather():
    merged = search_prs("is:merged")
    open_ = search_prs("is:open")
    repos = {_repo(i) for i in merged["items"] + open_["items"]}
    recent = sorted(merged["items"], key=_merged_at, reverse=True)[:4]
    return {
        "merged": merged["total_count"],
        "open": open_["total_count"],
        "repos": len(repos),
        "contributions": contributions(),
        "recent": [{"repo": _repo(i), "when": rel_time(_merged_at(i))}
                   for i in recent],
    }


def build(pal, d):
    stats = []
    if d["contributions"] is not None:
        stats.append((f"{d['contributions']:,}", "CONTRIBUTIONS · PAST YEAR"))
    stats += [(d["merged"], "UPSTREAM PRS MERGED"),
              (d["open"], "IN REVIEW"),
              (d["repos"], "REPOS CONTRIBUTED TO")]
    blocks = ""
    x = 28
    for num, label in stats:
        blocks += (
            f'<text x="{x}" y="100" font-size="30" font-weight="700" '
            f'fill="{pal["accent"]}">{num}</text>'
            f'<text x="{x}" y="122" font-size="11" letter-spacing="1" '
            f'fill="{pal["dim"]}">{label}</text>')
        x += 198
    items = ""
    for idx, it in enumerate(d["recent"]):
        ix = 28 + (idx % 2) * 396
        iy = 192 + (idx // 2) * 24
        items += (
            f'<text x="{ix}" y="{iy}" font-size="13">'
            f'<tspan fill="{pal["accent"]}">&#9642;</tspan>'
            f'<tspan fill="{pal["text"]}" font-weight="600"> '
            f'{html.escape(it["repo"])}</tspan>'
            f'<tspan fill="{pal["dim"]}"> · merged {it["when"]}</tspan>'
            f'</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Open-source activity metrics for {USER}">
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10" fill="{pal["bg"]}" stroke="{pal["border"]}"/>
<g font-family="&#39;Segoe UI&#39;,&#39;Helvetica Neue&#39;,Arial,sans-serif">
<text x="28" y="42" font-size="16" font-weight="600" fill="{pal["text"]}">Open-source activity</text>
<text x="{W - 28}" y="42" text-anchor="end" font-size="11" fill="{pal["dim"]}">updated {NOW:%d %b %Y} · refreshes every 6 h</text>
{blocks}
<line x1="28" y1="142" x2="{W - 28}" y2="142" stroke="{pal["border"]}"/>
<text x="28" y="168" font-size="11" letter-spacing="1.5" fill="{pal["dim"]}">RECENT MERGES</text>
{items}
</g>
</svg>
'''


def main():
    d = gather()
    (ROOT / "metrics-light.svg").write_text(build(LIGHT, d),
                                            encoding="utf-8")
    (ROOT / "metrics-dark.svg").write_text(build(DARK, d), encoding="utf-8")
    print(f"merged={d['merged']} open={d['open']} repos={d['repos']} "
          f"contributions={d['contributions']} recent={len(d['recent'])}")


if __name__ == "__main__":
    main()
