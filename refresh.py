#!/usr/bin/env python3
"""Refresh index.html's market strip, trend charts and macro-input trends.

Bakes data into index.html so the page is fully self-contained (no client fetch).
Runs headless in GitHub Actions daily.

Sources:
  - yfinance: gold/silver/DXY daily closes (3mo) -> market strip + trend charts + G/S ratio
  - FRED (public CSV, no key): DGS2 (2Y), DFII10 (10Y real), CPIAUCSL (CPI YoY),
    PAYEMS (NFP monthly change) -> "Makro-trend" section
"""
import re
import io
import csv
import sys
import json
import urllib.request
import datetime
from pathlib import Path

import yfinance as yf
import pandas as pd

HTML = Path(__file__).resolve().parent / "index.html"
TICKERS = {"gold": "GC=F", "silver": "SI=F", "dxy": "DX-Y.NYB"}
MONTHS = ["januari", "februari", "mars", "april", "maj", "juni", "juli",
          "augusti", "september", "oktober", "november", "december"]


def fetch_prices() -> pd.DataFrame:
    closes = {}
    for key, tkr in TICKERS.items():
        h = yf.Ticker(tkr).history(period="3mo", interval="1d")["Close"].dropna()
        if h.empty:
            raise RuntimeError(f"Ingen data for {key} ({tkr})")
        closes[key] = h
    df = pd.DataFrame(closes).dropna()
    if df.empty:
        raise RuntimeError("Ingen gemensam datumoverlappning")
    df["gs"] = df["gold"] / df["silver"]
    return df


def build_series(df: pd.DataFrame) -> dict:
    return {
        "dates": [f"{d.day}/{d.month}" for d in df.index],
        "gold":   [round(float(v), 1) for v in df["gold"]],
        "silver": [round(float(v), 2) for v in df["silver"]],
        "dxy":    [round(float(v), 2) for v in df["dxy"]],
        "gs":     [round(float(v), 1) for v in df["gs"]],
        "asof": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }


def fred(series_id: str, start: str) -> list:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=30).read().decode()
    rows = list(csv.reader(io.StringIO(data)))[1:]
    return [(r[0], float(r[1])) for r in rows if len(r) >= 2 and r[1] not in (".", "")]


def _dm(s): y, m, d = s.split("-"); return f"{int(d)}/{int(m)}"
def _myy(s): y, m, d = s.split("-"); return f"{int(m)}/{y[2:]}"


def build_macro() -> dict:
    out = {"asof": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}
    for key, sid in (("us2y", "DGS2"), ("real", "DFII10")):
        d = fred(sid, "2026-04-01")[-65:]
        out[key] = {"dates": [_dm(x[0]) for x in d],
                    "vals": [round(x[1], 2) for x in d], "unit": "%", "dec": 2}
    cpi = fred("CPIAUCSL", "2024-01-01")
    yoy = [(cpi[i][0], (cpi[i][1] / cpi[i - 12][1] - 1) * 100) for i in range(12, len(cpi))][-14:]
    out["cpi"] = {"dates": [_myy(x[0]) for x in yoy],
                  "vals": [round(x[1], 1) for x in yoy], "unit": "%", "dec": 1}
    pay = fred("PAYEMS", "2024-06-01")
    nfp = [(pay[i][0], pay[i][1] - pay[i - 1][1]) for i in range(1, len(pay))][-14:]
    out["nfp"] = {"dates": [_myy(x[0]) for x in nfp],
                  "vals": [round(x[1]) for x in nfp], "unit": "k", "dec": 0}
    return out


def inject(series: dict, macro: dict) -> None:
    html = HTML.read_text(encoding="utf-8")

    def swap(marker_id, obj, var):
        pat = re.compile(r'(<script id="%s">).*?(</script>)' % marker_id, re.S)
        payload = json.dumps(obj, ensure_ascii=False)
        return pat.subn(lambda m: m.group(1) + var + "=" + payload + ";" + m.group(2), html)

    html, n1 = swap("seriesdata", series, "window.__SERIES__")
    html, n2 = swap("macrodata", macro, "window.__MACRO__")
    now = datetime.date.today()
    datestr = f"{now.day} {MONTHS[now.month - 1]} {now.year}"
    html, n3 = re.subn(r'(<div class="eyebrow">[^<]*uppdaterad )[^<]*(</div>)',
                       lambda m: m.group(1) + datestr + m.group(2), html)
    if n1 == 0 or n2 == 0:
        print(f"VARNING: markers seriesdata:{n1} macrodata:{n2}", file=sys.stderr)
    HTML.write_text(html, encoding="utf-8")
    print(f"OK seriesdata:{n1} macrodata:{n2} eyebrow:{n3} datum '{datestr}'")


def main():
    df = fetch_prices()
    s = build_series(df)
    m = build_macro()
    print(f"Guld ${s['gold'][-1]:,.0f} Silver ${s['silver'][-1]} G/S {s['gs'][-1]} DXY {s['dxy'][-1]} "
          f"| 2Y {m['us2y']['vals'][-1]}% Real {m['real']['vals'][-1]}% CPI {m['cpi']['vals'][-1]}% NFP {m['nfp']['vals'][-1]:+.0f}k")
    inject(s, m)


if __name__ == "__main__":
    main()
