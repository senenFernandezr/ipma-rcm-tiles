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

Las teselas necesitan una app que acepte capas raster propias: **OsmAnd lo hace
en su versión gratuita** (ver más abajo). En DMD2 es de pago.

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

### OsmAnd — el camino recomendado

OsmAnd admite capas raster XYZ de forma nativa, con transparencia y control de
opacidad. Es exactamente lo que esta capa necesita, y funciona en la versión
gratuita.

**1. Instalar la fuente de teselas (un toque).** OsmAnd acepta *Magic URLs* que
crean la fuente ya configurada. Abre este enlace **en el móvil** y elige OsmAnd:

```
https://osmand.net/add-tile-source?name=RCM%20hoy%20(IPMA)&min_zoom=6&max_zoom=12&url_template=https://senenfernandezr.github.io/ipma-rcm-tiles/today/{z}/{x}/{y}.png
```

En el visor tienes ese enlace y el de mañana como botones, en *Instalar en
OsmAnd*. Si prefieres hacerlo a mano: *Menu → Configure map → Overlay map… →*
añadir fuente, con la URL de la tabla de arriba, zoom 6–12.

**2. Activar el plugin.** *Menu → Plugins → **Online Maps*** (gratuito).

**3. Ponerla como superposición.** *Menu → Configure map → **Overlay map…*** →
elige `RCM hoy (IPMA)`. El mapa offline de Portugal sigue debajo.

**4. Ajustar la caducidad.** *Menu → **Maps & Resources** → Local → Map sources
→* toca la fuente *→* **⋮** *→* **Edit**. Ahí está el campo **"Expire time"**, en
minutos: pon **120**.

No cuelga de *Configure map*, que es donde uno lo busca. Y su valor por defecto
es en blanco, que significa **no recargar nunca**: sin tocarlo, mañana seguirías
viendo el riesgo de hoy. Es el paso que más se olvida.

En ese mismo menú **⋮** está **"Clear all tiles"**, que borra la caché de la
fuente. Tenlo localizado: hay informes de que el refresco de teselas online no
siempre es fiable, y eso lo resuelve a mano.

**5. Opacidad.** Usa el deslizador de transparencia de la superposición. Las
teselas ya vienen semitransparentes (alfa 120), así que empieza con el
deslizador al máximo y bájalo solo si tapa demasiado.

Sobre el zoom: la fuente se declara **6–12** porque es lo que existe de verdad.
Al acercar más, OsmAnd reescala la tesela de z12. Si en tu versión la capa
desapareciera por encima de z12, edita la fuente y sube el *max zoom* a 19.

### Importar tus propios tracks GPX en OsmAnd

Dos caminos, según dónde tengas el fichero:

- **Desde un gestor de archivos, correo o mensajería:** toca el `.gpx` y elige
  **"Open in OsmAnd"**. Aterriza en la carpeta **Import** de *My Places*.
- **Desde la app:** *Menu → My Places → **Tracks*** y selecciona el fichero. Si
  el GPX trae varios tracks, puedes importarlo entero o elegir cuáles.

Además, *"tracks manually added to the OsmAnd folder on your device are
automatically imported without restarting the application"* — si copias los
`.gpx` a la carpeta de OsmAnd, aparecen solos.

Para verlos y darles estilo: *Menu → My Places → Tracks*, menú de tres puntos
del track → **"Show/Hide on map"** para mostrarlo, y **"Appearance"** para color
y grosor. Tus rutas y la capa de riesgo conviven sin problema: una es un track,
la otra una superposición raster.

### DMD2 — necesita licencia

*Map Settings → Online Map Layers → Add Custom Raster*, con la URL de `today`.
Pero *Online Map Layers* es de pago (**"Online Map Layers needs a license"**), y
sin licencia no hay forma: DMD2 **no dibuja superficies**, convierte cualquier
fichero importado en tracks, routes o waypoints. Probado con KML de polígonos
(entran como rutas) y con un tramado de líneas (descartado).

Lo que sí es gratis en DMD2 y complementa bien esto: el módulo de país
**Portugal *Avisos***, con alertas de incendio y cierres de carretera de ANEPC.
Eso cubre los incendios **activos**, que es justo lo que esta capa no hace.

### Otras apps

Cualquiera que acepte URLs XYZ: **OruxMaps** (fuentes en `onlinemapsources.xml`),
**Guru Maps**. Y para apps que dibujen superficies de verdad, están publicados
los KMZ con los concelhos fusionados por nivel (`rcm-today.kmz`,
`rcm-today-alto.kmz` y sus equivalentes de mañana).

### Si ves datos de ayer (caché)

Las apps guardan las teselas ya vistas. Si la capa no se actualiza:

- OsmAnd: baja el *Expire time* de la fuente (120 minutos va bien).
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
