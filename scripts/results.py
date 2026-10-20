"""Vypíše všechna čísla, která jsou uvedená v textu stránky, z dat vytvořených process.py.

Použití: python3 results.py <data_dir>
"""
import json, statistics, sys

DATA = sys.argv[1] if len(sys.argv) > 1 else "data"
heat = json.load(open(f"{DATA}/heat.json", encoding="utf-8"))
air = json.load(open(f"{DATA}/air.json", encoding="utf-8"))
praha = json.load(open(f"{DATA}/praha.json", encoding="utf-8"))

med = statistics.median
def share(xs, f):
    return round(sum(1 for x in xs if f(x)) / len(xs) * 100)
def change(k):  # změna 2011–2025 vs. 1961–1990 na každé stanici
    return [s[k][1] - s[k][0] for s in heat["stations"] if k in s]
def pct(k):  # relativní změna 2023–2025 vs. 2015–2017 na každé stanici
    return [(s[k][1] - s[k][0]) / s[k][0] * 100 for s in air["stations"] if k in s and s[k][0] > 0]
country = {c["cc"]: c for c in heat["countries"]}
cz, es = country["CZ"], country["ES"]

print("1. Přibývá horkých dnů?")
su = change("SU")
print(f"   letní dny (Tmax > 25 °C): medián změny {med(su):+.0f} dní za léto, nárůst na {share(su, lambda v: v > 0)} % z {len(su)} stanic")
print(f"   Česko: {cz['SU'][0]:.0f} -> {cz['SU'][1]:.0f} dní, Španělsko: {es['SU'][0]:.0f} -> {es['SU'][1]:.0f} dní")
print(f"   tropické noci: Česko {cz['TR'][0]:.1f} -> {cz['TR'][1]:.1f}, Španělsko {es['TR'][0]:.0f} -> {es['TR'][1]:.0f}")

print("2. Zlepšuje se vzduch?")
for k, who in (("NO2", 10), ("PM2.5", 5)):
    v = pct(k)
    print(f"   {k}: medián změny {med(v):+.0f} %, pokles na {share(v, lambda x: x < 0)} % z {len(v)} stanic; "
          f"medián {air['years'][-1]}: {air['series'][k]['all'][-1]:.0f} µg/m³ (WHO {who})")

print("3. Souvisí to spolu?")
pts = air["ozone_heat"]["points"]
mx = sum(p["su"] for p in pts) / len(pts); my = sum(p["o3"] for p in pts) / len(pts)
slope = sum((p["su"] - mx) * (p["o3"] - my) for p in pts) / sum((p["su"] - mx) ** 2 for p in pts)
print(f"   ozon × letní dny (země-rok): r = {air['ozone_heat']['r']:.2f}, n = {len(pts)}, "
      f"sklon = {slope:.2f} ozonového dne na 1 letní den navíc")

print("4. Jak silný je tepelný ostrov Prahy?")
for name, d in praha["diff"].items():
    print(f"   Klementinum − {name} ({praha['elev'][name]} m): noci teplejší o {d['late']:.1f} °C v 2011–2025 "
          f"({d['early']:.1f} °C v 1961–1990)")
print("   tropické noci 2011–2025: " + ", ".join(f"{n} {v[1]:.0f}" for n, v in praha["tr"].items()))
