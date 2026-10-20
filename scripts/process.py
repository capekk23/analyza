"""Zpracuje ECA&D indexy veder a EEA statistiky ovzduší do malých JSON souborů pro web.

Použití: python3 process.py <ecad_dir> <eea_csv> <out_dir>
  ecad_dir obsahuje podsložky SU/, TR/, WSDI/, TXx/ s rozbalenými ECA_index*.zip
"""
import csv, glob, json, math, os, re, statistics, sys
from collections import defaultdict

ECAD, EEA_CSV, OUT = sys.argv[1:4]
os.makedirs(OUT, exist_ok=True)

EU = {"AUSTRIA": "AT", "BELGIUM": "BE", "BULGARIA": "BG", "CROATIA": "HR", "CYPRUS": "CY",
      "CZECH REPUBLIC": "CZ", "CZECHIA": "CZ", "DENMARK": "DK", "ESTONIA": "EE", "FINLAND": "FI",
      "FRANCE": "FR", "GERMANY": "DE", "GREECE": "GR", "HUNGARY": "HU", "IRELAND": "IE", "ITALY": "IT",
      "LATVIA": "LV", "LITHUANIA": "LT", "LUXEMBOURG": "LU", "MALTA": "MT", "NETHERLANDS": "NL",
      "POLAND": "PL", "PORTUGAL": "PT", "ROMANIA": "RO", "SLOVAKIA": "SK", "SLOVENIA": "SI",
      "SPAIN": "ES", "SWEDEN": "SE"}
EU_ISO = set(EU.values()) | {"EL"}

def in_europe(lat, lon):
    return 34 <= lat <= 72 and -11 <= lon <= 35  # bez Kanárských ostrovů a zámořských území

def dms(s):
    sign = -1 if s.strip().startswith("-") else 1
    d, m, x = (abs(float(p)) for p in s.strip().lstrip("+-").split(":"))
    return sign * (d + m / 60 + x / 3600)

def r1(x, n=1):
    return None if x is None else round(x, n)

def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None

def slope(pairs):
    """Lineární trend (OLS) na rok."""
    n = len(pairs)
    if n < 3:
        return None
    mx = sum(p[0] for p in pairs) / n; my = sum(p[1] for p in pairs) / n
    sxx = sum((p[0] - mx) ** 2 for p in pairs)
    return sum((p[0] - mx) * (p[1] - my) for p in pairs) / sxx if sxx else None

def pearson(xs, ys):
    n = len(xs); mx = sum(xs) / n; my = sum(ys) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sx = math.sqrt(sum((a - mx) ** 2 for a in xs)); sy = math.sqrt(sum((b - my) ** 2 for b in ys))
    return sxy / (sx * sy)

# ---------------------------------------------------------------- ECA&D: vedra
INDICES = {"SU": 0.01, "TR": 0.01, "WSDI": 0.01, "TXx": 0.01}
BASE, RECENT = range(1961, 1991), range(2011, 2026)
YEARS = range(1950, 2026)

stations = {}
for line in open(glob.glob(f"{ECAD}/TR/stations_*.txt")[0], encoding="latin-1"):
    parts = line.split(",")
    if len(parts) < 6 or not parts[0].strip().isdigit():
        continue
    cc = EU.get(parts[2].strip())
    if not cc:
        continue
    lat, lon = dms(parts[3]), dms(parts[4])
    if in_europe(lat, lon):
        stations[int(parts[0])] = {"id": int(parts[0]), "name": parts[1].strip().title(), "cc": cc,
                                   "lat": round(lat, 3), "lon": round(lon, 3), "elev": int(parts[5])}

series = defaultdict(dict)  # (staid, idx) -> {year: value}
for idx, scale in INDICES.items():
    for path in glob.glob(f"{ECAD}/{idx}/index{idx}_*.txt"):
        staid = int(re.search(r"_(\d+)\.txt$", path).group(1))
        if staid not in stations:
            continue
        for line in open(path, encoding="latin-1"):
            f = line.split()
            if len(f) < 5 or not f[0].isdigit() or not f[1].isdigit():
                continue
            year, v = int(f[1]), int(f[4])  # letní pololetí (duben–září) – robustní i při chybějící zimě
            if v != -999999 and year in YEARS:
                series[(staid, idx)][year] = v * scale

heat_stations, anomalies = [], defaultdict(lambda: defaultdict(list))
seen = set()
for sid, st in sorted(stations.items()):
    # ECA&D má některé řady pod více ID (Klementinum/Klementinum2, Malaga/Malaga Puerto) – duplicity vyhodíme
    fingerprint = tuple(sorted(series.get((sid, "SU"), {}).items()))
    if fingerprint in seen:
        continue
    seen.add(fingerprint)
    s = series.get((sid, "SU"), {})
    nb = sum(1 for y in BASE if y in s); nr = sum(1 for y in RECENT if y in s)
    if nb < 25 or nr < 12:  # potřebujeme dlouhou a souvislou řadu
        continue
    rec = dict(st)
    for idx in INDICES:
        ser = series.get((sid, idx), {})
        b = mean([ser.get(y) for y in BASE]); r = mean([ser.get(y) for y in RECENT])
        if b is None or r is None or sum(1 for y in BASE if y in ser) < 25:
            continue
        rec[idx] = [r1(b), r1(r)]
        cell = (math.floor(st["lat"] / 2), math.floor(st["lon"] / 2))
        for y, v in ser.items():
            anomalies[idx][y].append((cell, v - b, st["cc"]))
    if "SU" in rec:
        heat_stations.append(rec)

def gridded(rows, cc=None):
    """Průměr přes 2°×2° buňky, ať Itálie s 1600 stanicemi nepřehluší zbytek."""
    cells = defaultdict(list)
    for cell, v, c in rows:
        if cc is None or c == cc:
            cells[cell].append(v)
    return mean([mean(v) for v in cells.values()]) if cells else None

heat_series = {idx: {"EU": [], "ES": [], "CZ": []} for idx in INDICES}
for idx in INDICES:
    for y in YEARS:
        for key in ("EU", "ES", "CZ"):
            heat_series[idx][key].append(r1(gridded(anomalies[idx][y], None if key == "EU" else key), 2))

heat_country = []
for cc in sorted({s["cc"] for s in heat_stations}):
    ss = [s for s in heat_stations if s["cc"] == cc]
    row = {"cc": cc, "n": len(ss)}
    for idx in INDICES:
        vals = [s[idx] for s in ss if idx in s]
        if vals:
            row[idx] = [r1(statistics.median(v[0] for v in vals)), r1(statistics.median(v[1] for v in vals))]
    heat_country.append(row)

print("heat stations:", len(heat_stations), file=sys.stderr)

# ---------------------------------------------------------------- EEA: ovzduší
POLS = ["NO2", "PM10", "PM2.5", "O3"]
AQ_YEARS = range(2013, 2026)
EARLY, LATE = range(2015, 2018), range(2023, 2026)
aq = defaultdict(dict)  # (station, pol) -> {year: value}
aq_meta = {}
for r in csv.DictReader(open(EEA_CSV, encoding="utf-8")):
    if r["Preliminary"] == "1" or not r["AirPollutionLevel"]:
        continue
    cc = "GR" if r["Country_ISO"] == "EL" else r["Country_ISO"]
    if cc not in EU_ISO:
        continue
    y = int(r["YearOfStatistics"])
    if y not in AQ_YEARS:
        continue
    cov = r["DataCoverage"]
    if cov and float(cov) < 75:
        continue
    lat, lon = float(r["LatitudeOfMeasurementStation"]), float(r["LongitudeOfMeasurementStation"])
    if not in_europe(lat, lon):
        continue
    sid = r["AirQualityStation"]
    aq[(sid, r["AirPollutant"])][y] = float(r["AirPollutionLevel"])
    aq_meta[sid] = {"id": sid, "name": r["StationName"], "cc": cc, "lat": round(lat, 3), "lon": round(lon, 3),
                    "type": r["TypeOfMeasurementStation"], "area": r["AreaOfMeasurementStation"]}

air_stations = {}
air_series = {p: {"all": [], "Traffic": [], "Background": [], "Industrial": []} for p in POLS}
panel = defaultdict(list)
for (sid, pol), ser in aq.items():
    e = mean([ser.get(y) for y in EARLY]); l = mean([ser.get(y) for y in LATE])
    if e is None or l is None or sum(1 for y in range(2015, 2026) if y in ser) < 9:
        continue
    st = air_stations.setdefault(sid, dict(aq_meta[sid]))
    st[pol] = [r1(e), r1(l)]
    panel[pol].append(sid)

for pol in POLS:
    for y in AQ_YEARS:
        for t in air_series[pol]:
            vals = [aq[(sid, pol)][y] for sid in panel[pol]
                    if y in aq[(sid, pol)] and (t == "all" or aq_meta[sid]["type"] == t)]
            air_series[pol][t].append(r1(statistics.median(vals)) if len(vals) >= 10 else None)

air_country = []
for cc in sorted({s["cc"] for s in air_stations.values()}):
    row = {"cc": cc}
    for pol in POLS:
        vals = [s[pol] for s in air_stations.values() if s["cc"] == cc and pol in s]
        if len(vals) >= 3:
            row[pol] = [r1(statistics.median(v[0] for v in vals)), r1(statistics.median(v[1] for v in vals)), len(vals)]
    air_country.append(row)

print("air stations:", len(air_stations), {p: len(panel[p]) for p in POLS}, file=sys.stderr)

# ---------------------------------------------------------------- ozon × vedra
# Pro každou zemi a rok: medián dnů s ozonem nad 120 µg/m³ a průměrná odchylka letních dnů (SU).
# Od obou odečteme průměr dané země, ať srovnáváme jen rok od roku (ne Itálii se Švédskem).
o3_cy = defaultdict(list)
for (sid, pol), ser in aq.items():
    if pol == "O3":
        for y, v in ser.items():
            o3_cy[(aq_meta[sid]["cc"], y)].append(v)
su_cy = {}
for y in AQ_YEARS:
    for cc in {c for _, _, c in anomalies["SU"][y]}:
        su_cy[(cc, y)] = gridded(anomalies["SU"][y], cc)

pts = []
for (cc, y), vals in o3_cy.items():
    if len(vals) >= 5 and su_cy.get((cc, y)) is not None:
        pts.append({"cc": cc, "y": y, "o3": statistics.median(vals), "su": su_cy[(cc, y)]})
by_cc = defaultdict(list)
for p in pts:
    by_cc[p["cc"]].append(p)
scatter = []
for cc, ps in by_cc.items():
    if len(ps) < 8:
        continue
    mo = mean([p["o3"] for p in ps]); ms = mean([p["su"] for p in ps])
    for p in ps:
        scatter.append({"cc": cc, "y": p["y"], "o3": r1(p["o3"] - mo), "su": r1(p["su"] - ms)})
r_ozone = pearson([p["su"] for p in scatter], [p["o3"] for p in scatter])
print("ozone~heat r =", round(r_ozone, 3), "n =", len(scatter), file=sys.stderr)

# ---------------------------------------------------------------- výstup
json.dump({"stations": heat_stations, "years": list(YEARS), "series": heat_series, "countries": heat_country,
           "base": [BASE.start, BASE.stop - 1], "recent": [RECENT.start, RECENT.stop - 1]},
          open(f"{OUT}/heat.json", "w"), ensure_ascii=False, separators=(",", ":"))
json.dump({"stations": list(air_stations.values()), "years": list(AQ_YEARS), "series": air_series,
           "countries": air_country, "early": [EARLY.start, EARLY.stop - 1], "late": [LATE.start, LATE.stop - 1],
           "ozone_heat": {"r": round(r_ozone, 3), "points": scatter}},
          open(f"{OUT}/air.json", "w"), ensure_ascii=False, separators=(",", ":"))

# ---------------------------------------------------------------- tabulka zemí ke stažení
NAMES = {v: k.title() for k, v in EU.items() if k != "CZECHIA"}
with open(f"{OUT}/zeme.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["zeme", "kod", "meteostanic",
                "letni_dny_1961_1990", "letni_dny_2011_2025", "tropicke_noci_1961_1990", "tropicke_noci_2011_2025",
                "stanic_ovzdusi_no2", "no2_2015_2017", "no2_2023_2025", "no2_zmena_pct",
                "stanic_ovzdusi_pm25", "pm25_2015_2017", "pm25_2023_2025", "pm25_zmena_pct"])
    air_by = {c["cc"]: c for c in air_country}
    for h in heat_country:
        a = air_by.get(h["cc"], {})
        def pol(p):
            if p not in a:
                return ["", "", "", ""]
            e, l, n = a[p]
            return [n, e, l, r1((l - e) / e * 100) if e else ""]
        w.writerow([NAMES.get(h["cc"], h["cc"]), h["cc"], h["n"],
                    *h.get("SU", ["", ""]), *h.get("TR", ["", ""]), *pol("NO2"), *pol("PM2.5")])
