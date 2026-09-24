# ipma-rcm-tiles

Capa de teselas XYZ con el **risco de incêndio (RCM) del IPMA** por concelho de
Portugal continental, pensada para usarla como *Custom Raster* en **DMD2**
(Drive Mode Dashboard) u otra app que acepte URLs `{z}/{x}/{y}.png`.

> ⚠️ Es la **previsión meteorológica de riesgo de incendio**, no incendios activos.
> Datos: [IPMA open-data](https://api.ipma.pt/open-data/forecast/meteorology/rcm/rcm-d0.json).
> Geometrías: CAOP (DGT), nivel concelho, con código DICO.

## URLs

Sustituye `<usuario>` por tu usuario de GitHub:

| Capa | URL |
|---|---|
| Hoy | `https://<usuario>.github.io/ipma-rcm-tiles/today/{z}/{x}/{y}.png` |
| Mañana | `https://<usuario>.github.io/ipma-rcm-tiles/tomorrow/{z}/{x}/{y}.png` |
| Visor de prueba | `https://<usuario>.github.io/ipma-rcm-tiles/` |
| Metadatos | `https://<usuario>.github.io/ipma-rcm-tiles/meta.json` |

Zooms disponibles: **6 – 12** (por encima de 12, la app debe escalar la tesela de z12).
Cobertura: Portugal continental (lon −9,6…−6,1 / lat 36,9…42,2). Fuera de ese
recuadro no hay teselas.

## Leyenda

| RCM | Nivel | Color |
|---|---|---|
| 1 | Reduzido | `#2E9E44` |
| 2 | Moderado | `#F2D21B` |
| 3 | Elevado | `#F28C1B` |
| 4 | Muito elevado | `#E0261B` |
| 5 | Máximo | `#7A0E0E` |

Relleno con alfa 120/255 para que se siga viendo el mapa base. Bordes de
concelho a partir de z9.

## Configuración en DMD2

1. *Map Settings → Online Map Layers → Add Custom Raster*.
2. Pega la URL de la capa **today**.
3. Zoom mínimo 6, zoom máximo 12.
4. Si DMD2 usa otra sintaxis de marcadores (`$z/$x/$y` en vez de `{z}/{x}/{y}`),
   adáptala; el servidor solo sirve ficheros estáticos.

### Si ves datos de ayer (caché)

DMD2 puede guardar las teselas en su *auto-cache*. Si la capa no se actualiza:

- Desactiva el auto-cache para esa capa, o borra su caché.
- Plan B: publicar además una ruta con fecha (`/d/AAAA-MM-DD/{z}/{x}/{y}.png`)
  y cambiar la URL a diario. No está activado para no duplicar el tamaño del
  despliegue; se añade fácil en `scripts/build_tiles.py` (copiar `today/` a
  `d/<dataPrev>/`).

## Cómo funciona

```
data/concelhos.geojson     278 concelhos (EPSG:4326, simplificado ~0,001°)
scripts/prepare_concelhos.py   genera ese GeoJSON desde la CAOP (uso puntual)
scripts/build_tiles.py     descarga RCM d0/d1 y rasteriza las teselas
site/index.html            visor Leaflet, se copia a public/
.github/workflows/build.yml  4 veces/dia: build + deploy a Pages
```

- **Cuándo se actualiza:** IPMA regenera `rcm-d0.json` y `rcm-d1.json` una vez
  al día, sobre las **09:35 UTC** (el `Last-Modified` de la respuesta coincide
  con el `fileDate` del JSON). El workflow se lanza a las **09:45, 11:45, 14:45
  y 18:45 UTC**: la primera justo después de la publicación y las otras como
  reintento si IPMA se retrasa o corrige el dato, o si GitHub retrasa el cron.
- Antes de las ~09:35 UTC, `rcm-d0` puede seguir apuntando al día anterior. No es
  un fallo, así que el build no aborta: se marca `"stale": true` en `meta.json`
  y el visor lo advierte en rojo.
- Las teselas **no se commitean**: se generan en cada ejecución y solo viajan en
  el artefacto de Pages (~4.400 PNG por capa, ~45 MB, ~1 min de build).
- Dentro del recuadro, las teselas sin dato se escriben como PNG transparente
  para no provocar 404 en la app.
- Si la API de IPMA falla o devuelve datos vacíos, el script **sale con error**:
  la Action falla y se mantiene el despliegue anterior. Nunca se publica una capa vacía.

## Forzar una regeneración

Desde la web: *Actions → build-and-deploy → Run workflow*.

Con la CLI:

```bash
gh workflow run build-and-deploy --repo <usuario>/ipma-rcm-tiles
```

## Desarrollo en local

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python scripts/build_tiles.py --zooms 6-9 --layers today
python -m http.server 8765 -d public
```

Luego abre `http://localhost:8765`.

Regenerar las geometrías (solo si sale una CAOP nueva):

```bash
.venv/Scripts/python -m pip install -r requirements-prepare.txt
.venv/Scripts/python scripts/prepare_concelhos.py
```

## Licencia y créditos

- Datos RCM: IPMA, open-data.
- Límites administrativos: CAOP / DGT (vía
  [nmota/caop_GeoJSON](https://github.com/nmota/caop_GeoJSON)).
- Mapa base del visor: OpenStreetMap.
