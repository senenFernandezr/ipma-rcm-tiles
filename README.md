# ipma-rcm-tiles

Capa de teselas XYZ con el **risco de incêndio (RCM) del IPMA** por concelho de
Portugal continental, pensada para usarla como *Custom Raster* en **DMD2**
(Drive Mode Dashboard) u otra app que acepte URLs `{z}/{x}/{y}.png`.

> ⚠️ Es la **previsión meteorológica de riesgo de incendio**, no incendios activos.
> Datos: [IPMA open-data](https://api.ipma.pt/open-data/forecast/meteorology/rcm/rcm-d0.json).
> Geometrías: CAOP (DGT), nivel concelho, con código DICO.

## URLs

| Capa | URL |
|---|---|
| Hoy | `https://senenfernandezr.github.io/ipma-rcm-tiles/today/{z}/{x}/{y}.png` |
| Mañana | `https://senenfernandezr.github.io/ipma-rcm-tiles/tomorrow/{z}/{x}/{y}.png` |
| Visor de prueba | `https://senenfernandezr.github.io/ipma-rcm-tiles/` |
| Metadatos | `https://senenfernandezr.github.io/ipma-rcm-tiles/meta.json` |
| KMZ hoy (nivel 4-5) | `https://senenfernandezr.github.io/ipma-rcm-tiles/rcm-today-alto.kmz` |
| KMZ hoy (todos) | `https://senenfernandezr.github.io/ipma-rcm-tiles/rcm-today.kmz` |

Las teselas necesitan una app que acepte capas raster propias; los **KMZ
funcionan en DMD2 sin licencia** (ver más abajo).

Zooms generados: **6 – 12**. Cobertura: Portugal continental
(lon −9,6…−6,1 / lat 36,9…42,2); fuera de ese recuadro no hay teselas.

### Zoom por encima de 12

El dato es por concelho, así que no gana nada con más resolución: lo correcto es
que la app **reescale** la tesela de z12. En el visor lo hace Leaflet con
`maxNativeZoom: 12`, y se ve bien hasta z19.

En DMD2, pon el **zoom máximo de la capa en 19** (no en 12). Si aun así la capa
desaparece al pasar de z12, es que la app no reescala y hay que generar esos
zooms. Para no multiplicar el número de teselas, se generan **solo para el
riesgo alto** y sin rellenar las vacías:

```bash
python scripts/build_tiles.py --extra-zooms 13-14 --extra-min-rcm 4
```

Eso añade z13 y z14 únicamente donde el riesgo es 4 o 5 (las zonas de riesgo
bajo dejan de tener tesela a partir de z13, que es justo lo que interesa ver de
cerca). Para activarlo de forma permanente, añade esos argumentos al paso
“Generar teselas” de `.github/workflows/build.yml`.

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

## Configuración en el móvil

Hay dos formas de consumir esto, según si tienes licencia de DMD2 o no.

### DMD2 sin licencia — ficheros KMZ

*Add Custom Raster* vive dentro de *Online Map Layers*, y la documentación
oficial dice que **"Online Map Layers needs a license"**. Pero **abrir ficheros
sí es gratis**: DMD2 importa GPX, KML, KMZ, GeoJSON, TCX, FIT, ITN y CSV, y los
KML/KMZ incluyen *"lines, points, areas and timed tracks"* — áreas incluidas.

Así que el build publica la misma capa como polígonos KMZ:

| Fichero | Contenido |
|---|---|
| `rcm-today-alto.kmz` | hoy, solo niveles 4 y 5 |
| `rcm-today.kmz` | hoy, los cinco niveles |
| `rcm-tomorrow-alto.kmz` | mañana, solo niveles 4 y 5 |
| `rcm-tomorrow.kmz` | mañana, los cinco niveles |

Unos 90–120 KB cada uno. Los concelhos del mismo nivel van **fusionados** en un
solo polígono por nivel: quita las fronteras interiores, así que el fichero pesa
menos y se lee mejor en marcha.

Cómo usarlo:

1. En el móvil, abre el visor y toca el enlace del fichero que quieras (están en
   *Ficheiros KMZ*, dentro del panel de la leyenda).
2. En la notificación de descarga, **Abrir con → Import to DMD**. También vale
   compartir el fichero desde el gestor de archivos.
3. Aparece en *Loaded GPX Files*, en el mapa.

**Hay que repetirlo cada día**, porque la previsión cambia. La URL es fija, así
que puedes dejar un acceso directo en la pantalla de inicio y son dos toques.

Dos avisos honestos: la documentación confirma que las áreas se importan, pero
**no dice si respeta el color de relleno** del KML. Si DMD2 dibuja solo el
contorno, se sigue viendo perfectamente qué zonas están en nivel 4–5, que es lo
que importa. Y el KML no es una capa de teselas: no se reescala ni se recorta por
zoom, se dibuja tal cual.

### Con licencia (DMD2, OsmAnd, otras) — capa raster XYZ

Cualquier app que acepte una URL de teselas XYZ. Pon siempre **zoom mínimo 6 y
zoom máximo 19** (las teselas llegan a z12; el 19 es para que la app reescale al
acercar en vez de dejar la capa en blanco). Si no reescala, mira *Zoom por
encima de 12*, más arriba.

- **DMD2:** *Map Settings → Online Map Layers → Add Custom Raster*, con la URL de
  `today` y, si existe el interruptor, marcada como overlay. Con la licencia,
  DMD2 ya trae además sus capas *Active Fires* y *Fire Danger*; esta sigue
  teniendo sentido porque es el índice oficial del IPMA por concelho.
- **OsmAnd:** *Menu → Plugins → **Online Maps***, luego *Menu → Configure map →
  **Overlay map…*** → añadir fuente. Acepta `{z}/{x}/{y}` y `{0}/{1}/{2}`. Pon
  *Expire time* en unos **120 minutos**, o cacheará el riesgo de ayer. Deja el
  deslizador de transparencia al máximo: las teselas ya vienen semitransparentes.
- **OruxMaps** (fuentes en `onlinemapsources.xml`) y **Guru Maps** también
  aceptan URLs XYZ en su nivel gratuito, sin el límite de mapas de OsmAnd.

### Si ves datos de ayer (caché)

Las apps guardan las teselas ya vistas. Si la capa no se actualiza:

- OsmAnd: baja el *Expire time* de la fuente.
- DMD2: *Clear Auto-Cache*, o desactiva el auto-cache para esa capa.
- Plan B: publicar además una ruta con fecha (`/d/AAAA-MM-DD/{z}/{x}/{y}.png`)
  y cambiar la URL a diario. No está activado para no duplicar el tamaño del
  despliegue; se añade fácil en `scripts/build_tiles.py` (copiar `today/` a
  `d/<dataPrev>/`).

## Cómo funciona

```
data/concelhos.geojson     278 concelhos (EPSG:4326, simplificado ~0,001°)
scripts/prepare_concelhos.py   genera ese GeoJSON desde la CAOP (uso puntual)
scripts/build_tiles.py     descarga RCM d0/d1, rasteriza las teselas y
                           genera los KML/KMZ
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
gh workflow run build-and-deploy --repo senenFernandezr/ipma-rcm-tiles
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
