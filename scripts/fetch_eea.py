"""Stáhne roční statistiky kvality ovzduší po stanicích z EEA (ArcGIS služba AQ_Statistics_WM)."""
import csv, json, sys, time, urllib.parse, urllib.request

URL = "https://eeha.discomap.eea.europa.eu/arcgis/rest/services/AirQuality/AQ_Statistics_WM/MapServer/0/query"
SERIES = [("NO2", "P1Y"), ("PM10", "P1Y"), ("PM2.5", "P1Y"), ("O3", "P1Y-dmaxAbove120")]
FIELDS = ["AirPollutant", "DataAggregationProcess", "YearOfStatistics", "AirQualityStation", "StationName",
          "Country_ISO", "TypeOfMeasurementStation", "AreaOfMeasurementStation", "LatitudeOfMeasurementStation",
          "LongitudeOfMeasurementStation", "AirPollutionLevel", "DataCoverage", "Preliminary"]

def query(where, offset):
    params = {"where": where, "outFields": ",".join(FIELDS), "returnGeometry": "false", "orderByFields": "OBJECTID",
              "resultOffset": offset, "resultRecordCount": 1000, "f": "json"}
    req = urllib.request.Request(URL, data=urllib.parse.urlencode(params).encode())
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except Exception as e:
            print("retry", e, file=sys.stderr); time.sleep(3 * (attempt + 1))
    raise RuntimeError("failed")

out = csv.DictWriter(open(sys.argv[1], "w", newline=""), fieldnames=FIELDS)
out.writeheader()
for pol, agg in SERIES:
    where = f"AirPollutant='{pol}' AND DataAggregationProcess='{agg}'"
    offset = 0
    while True:
        d = query(where, offset)
        feats = d.get("features", [])
        for f in feats:
            out.writerow({k: f["attributes"].get(k) for k in FIELDS})
        offset += len(feats)
        if not feats or not d.get("exceededTransferLimit"):
            break
    print(pol, agg, offset, file=sys.stderr)
