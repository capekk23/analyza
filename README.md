# Horké dny a kvalita ovzduší v EU

Živě: https://analýza.kacapek.dev

Školní analýza dvou otevřených datových sad:

1. Přibývá horkých dnů? (ECA&D, meteostanice v EU, 1950–2025)
2. Zlepšuje se vzduch? (EEA, stanice kvality ovzduší v EU, 2013–2025)
3. Souvisí to spolu? (ozon × letní dny)
4. Roste tepelný ostrov Prahy? (ECA&D, Klementinum vs. Ruzyně, Brandýs, Ondřejov)

```
index.html        stránka (D3 z CDN, žádný build)
favicon.svg
data/heat.json    zpracované teplotní indexy po stanicích
data/air.json     zpracované roční statistiky ovzduší
data/zeme.csv     výsledky po zemích
data/praha.json   tepelný ostrov Prahy (Klementinum vs. okolí)
scripts/          stažení a zpracování dat (čistý Python, bez knihoven)
```

## Lokálně

```bash
python3 -m http.server 8765
```

## Přepočet dat

```bash
# ovzduší (EEA)
python3 scripts/fetch_eea.py /cesta/aq_stats.csv
# teploty (ECA&D): stáhnout a rozbalit do ecad/SU, ecad/TR, ecad/WSDI, ecad/TXx, ecad/TN
#   https://knmi-ecad-assets-prd.s3.amazonaws.com/download/millennium/data/ECA_index{SU,TR,WSDI,TXx,TN}.zip
python3 scripts/process.py /cesta/ecad /cesta/aq_stats.csv data
```

## Nasazení (Raspberry Pi, nginx)

```bash
rsync -az --delete index.html favicon.svg data k@<pi>:analyza-upload/
ssh k@<pi> 'sudo rsync -a --delete ~/analyza-upload/ /var/www/analyza/'
```

nginx: `/etc/nginx/sites-available/analyza`, certifikát Let's Encrypt (`analyza.kacapek.dev`, `xn--analza-eza.kacapek.dev`).

## Zdroje a licence

- ECA&D: Klein Tank, A.M.G. et al., 2002, Int. J. Climatol. 22, 1441–1453. Data pouze pro nekomerční výzkum a vzdělávání.
- EEA: Air Quality Statistics (AQ_Statistics_WM), volně s uvedením zdroje.
- Hranice států: Natural Earth (world-atlas).
