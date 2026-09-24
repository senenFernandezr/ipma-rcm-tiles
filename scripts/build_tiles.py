"""Genera las teselas XYZ del riesgo de incendio (RCM) de IPMA por concelho.

Salida:
    public/today/{z}/{x}/{y}.png
    public/tomorrow/{z}/{x}/{y}.png
    public/meta.json
    public/index.html   (copia de site/index.html)

Si la API de IPMA falla o devuelve datos vacios el script termina con codigo != 0,
de modo que la GitHub Action falla y se mantiene el despliegue anterior.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import mercantile
import requests
from PIL import Image, ImageDraw
from shapely.geometry import box, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
CONCELHOS = ROOT / "data" / "concelhos.geojson"
SITE = ROOT / "site"
OUTDIR = ROOT / "public"

API = "https://api.ipma.pt/open-data/forecast/meteorology/rcm/rcm-d{day}.json"

# Portugal continental, con un pequeno margen.
BBOX = (-9.60, 36.90, -6.10, 42.20)
ZOOMS = range(6, 13)

TILE = 256
SS = 2            # supersampling para antialias
ALPHA = 120       # transparencia del relleno (0-255)
BORDER_MIN_Z = 9
BORDER_RGBA = (90, 90, 90, 140)

RCM_HEX = {
    1: "#2E9E44",   # reducido
    2: "#F2D21B",   # moderado
    3: "#F28C1B",   # elevado
    4: "#E0261B",   # muy elevado
    5: "#7A0E0E",   # maximo
}
# Etiquetas en espanol; el indice es el oficial del IPMA (reduzido, moderado,
# elevado, muito elevado, maximo).
RCM_LABEL = {
    1: "Reducido",
    2: "Moderado",
    3: "Elevado",
    4: "Muy elevado",
    5: "Maximo",
}


def hex_to_rgba(h: str, alpha: int) -> tuple[int, int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


FILL = {k: hex_to_rgba(v, ALPHA) for k, v in RCM_HEX.items()}


# --------------------------------------------------------------------------- #
# Datos IPMA
# --------------------------------------------------------------------------- #
def fetch_rcm(day: int, retries: int = 3) -> dict:
    url = API.format(day=day)
    last = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, timeout=60,
                             headers={"User-Agent": "ipma-rcm-tiles/1.0"})
            r.raise_for_status()
            data = r.json()
        except Exception as exc:  # noqa: BLE001
            last = exc
            print("[warn] intento %d/%d fallido para %s: %s" % (attempt, retries, url, exc),
                  file=sys.stderr)
            time.sleep(3 * attempt)
            continue

        local = data.get("local")
        if not isinstance(local, dict) or not local:
            last = RuntimeError("campo 'local' ausente o vacio")
            print("[warn] intento %d/%d: %s" % (attempt, retries, last), file=sys.stderr)
            time.sleep(3 * attempt)
            continue

        levels: dict[str, int] = {}
        for key, entry in local.items():
            dico = str(entry.get("dico") or entry.get("DICO") or key).zfill(4)
            rcm = (entry.get("data") or {}).get("rcm")
            if rcm is None:
                continue
            try:
                rcm = int(rcm)
            except (TypeError, ValueError):
                continue
            if rcm in FILL:
                levels[dico] = rcm

        if not levels:
            last = RuntimeError("ningun valor de rcm valido")
            print("[warn] intento %d/%d: %s" % (attempt, retries, last), file=sys.stderr)
            time.sleep(3 * attempt)
            continue

        print("[ok] d%d: %d concelhos con dato (dataPrev=%s, fileDate=%s)"
              % (day, len(levels), data.get("dataPrev"), data.get("fileDate")))
        return {
            "dataPrev": data.get("dataPrev"),
            "dataRun": data.get("dataRun"),
            "fileDate": data.get("fileDate"),
            "levels": levels,
        }

    raise SystemExit("[error] no se pudieron obtener datos de %s: %s" % (url, last))


# --------------------------------------------------------------------------- #
# Geometria
# --------------------------------------------------------------------------- #
def load_concelhos() -> list:
    if not CONCELHOS.exists():
        raise SystemExit("[error] falta %s. Ejecuta scripts/prepare_concelhos.py" % CONCELHOS)
    fc = json.loads(CONCELHOS.read_text(encoding="utf-8-sig"))
    out = []
    for feat in fc["features"]:
        props = feat.get("properties") or {}
        dico = str(props.get("dico") or props.get("DICO") or "").zfill(4)
        geom = shape(feat["geometry"])
        if geom.is_empty:
            continue
        out.append((dico, geom))
    if not out:
        raise SystemExit("[error] concelhos.geojson sin geometrias")
    print("[ok] %d poligonos de concelho cargados" % len(out))
    return out


def lonlat_to_norm(lon: float, lat: float) -> tuple[float, float]:
    """Web Mercator normalizado (0..1, origen arriba-izquierda)."""
    lat = max(min(lat, 85.05112878), -85.05112878)
    x = (lon + 180.0) / 360.0
    s = math.sin(math.radians(lat))
    y = 0.5 - math.log((1.0 + s) / (1.0 - s)) / (4.0 * math.pi)
    return x, y


def ring_to_px(coords, z: int, tx: int, ty: int) -> list:
    n = float(1 << z)
    size = TILE * SS
    pts = []
    for coord in coords:
        lon, lat = coord[0], coord[1]
        nx, ny = lonlat_to_norm(lon, lat)
        pts.append(((nx * n - tx) * size, (ny * n - ty) * size))
    return pts


def polygons_of(geom):
    if geom.is_empty:
        return
    gtype = geom.geom_type
    if gtype == "Polygon":
        yield geom
    elif gtype in ("MultiPolygon", "GeometryCollection"):
        for part in geom.geoms:
            yield from polygons_of(part)


def render_tile(tile, entries, draw_borders: bool) -> Image.Image:
    """entries: lista de (geometria_recortada, rcm)."""
    size = TILE * SS
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if entries:
        drw = ImageDraw.Draw(img)
        # 1) rellenos
        for geom, rcm in entries:
            color = FILL[rcm]
            for poly in polygons_of(geom):
                ext = ring_to_px(poly.exterior.coords, tile.z, tile.x, tile.y)
                if len(ext) >= 3:
                    drw.polygon(ext, fill=color)
                for hole in poly.interiors:
                    ring = ring_to_px(hole.coords, tile.z, tile.x, tile.y)
                    if len(ring) >= 3:
                        drw.polygon(ring, fill=(0, 0, 0, 0))
        # 2) bordes de concelho
        if draw_borders:
            width = max(1, SS)
            for geom, _rcm in entries:
                for poly in polygons_of(geom):
                    for ring in [poly.exterior] + list(poly.interiors):
                        pts = ring_to_px(ring.coords, tile.z, tile.x, tile.y)
                        if len(pts) >= 2:
                            drw.line(pts, fill=BORDER_RGBA, width=width, joint="curve")
    if SS > 1:
        # premultiplicado (modo RGBa) para evitar halos oscuros al reducir
        img = img.convert("RGBa").resize((TILE, TILE), Image.LANCZOS).convert("RGBA")
    return img


def build_layer(name: str, levels: dict, concelhos: list, outdir: Path,
                specs: list) -> int:
    """specs: lista de (zoom, min_rcm, fill_empty).

    min_rcm     solo se dibujan los concelhos con rcm >= min_rcm.
    fill_empty  si True, las teselas sin contenido se escriben transparentes
                (evita 404); si False no se escriben (zooms extra).
    """
    layer_dir = outdir / name
    if layer_dir.exists():
        shutil.rmtree(layer_dir)

    all_dicos = set(d for d, _g in concelhos)
    with_data = [(d, g) for d, g in concelhos if d in levels]

    missing = sorted(all_dicos - set(levels))
    if missing:
        print("[warn] %s: %d concelhos sin dato RCM: %s%s"
              % (name, len(missing), ", ".join(missing[:15]),
                 " ..." if len(missing) > 15 else ""), file=sys.stderr)
    orphans = sorted(set(levels) - all_dicos)
    if orphans:
        print("[warn] %s: %d DICO del JSON sin poligono: %s%s"
              % (name, len(orphans), ", ".join(orphans[:15]),
                 " ..." if len(orphans) > 15 else ""), file=sys.stderr)

    blank = Image.new("RGBA", (TILE, TILE), (0, 0, 0, 0))
    total = 0
    for z, min_rcm, fill_empty in specs:
        dpp = 360.0 / (TILE * (1 << z))          # grados por pixel
        tol = dpp * 0.4
        simplified = []
        for dico, geom in with_data:
            if levels[dico] < min_rcm:
                continue
            g = geom.simplify(tol, preserve_topology=True) if tol > 0 else geom
            if not g.is_empty:
                simplified.append((dico, g))
        tree = STRtree([g for _d, g in simplified])

        tiles = list(mercantile.tiles(BBOX[0], BBOX[1], BBOX[2], BBOX[3], [z]))
        count_z = 0
        for tile in tiles:
            b = mercantile.bounds(tile)
            pad = dpp * 4
            clip = box(b.west - pad, b.south - pad, b.east + pad, b.north + pad)
            entries = []
            for idx in tree.query(clip):
                dico, geom = simplified[int(idx)]
                piece = geom.intersection(clip)
                if piece.is_empty:
                    continue
                entries.append((piece, levels[dico]))

            if not entries and not fill_empty:
                continue
            path = layer_dir / str(z) / str(tile.x) / ("%d.png" % tile.y)
            path.parent.mkdir(parents=True, exist_ok=True)
            if entries:
                img = render_tile(tile, entries, draw_borders=z >= BORDER_MIN_Z)
                img.save(path, "PNG", optimize=True)
            else:
                blank.save(path, "PNG", optimize=True)
            count_z += 1
        total += count_z
        extra = "" if min_rcm <= 1 else " (solo rcm>=%d)" % min_rcm
        print("[ok] %s z%d: %d teselas%s" % (name, z, count_z, extra))
    return total


# --------------------------------------------------------------------------- #
# KML: misma capa en formato de fichero, para apps que no admiten raster propio
# (el Add Custom Raster de DMD2 necesita licencia; abrir KML/KMZ/GeoJSON no).
# --------------------------------------------------------------------------- #
KML_SIMPLIFY = 0.002      # ~200 m, de sobra a escala de conduccion
KML_PRECISION = 5



def kml_color(hexrgb: str, alpha: int) -> str:
    """KML usa aabbggrr, no #rrggbb."""
    h = hexrgb.lstrip("#")
    return "%02x%s%s%s" % (alpha, h[4:6], h[2:4], h[0:2])


def _kml_ring(ring) -> str:
    fmt = "%%.%df,%%.%df" % (KML_PRECISION, KML_PRECISION)
    return " ".join(fmt % (c[0], c[1]) for c in ring.coords)


def _kml_polygons(geom) -> str:
    out = []
    for poly in polygons_of(geom):
        parts = ["<Polygon><outerBoundaryIs><LinearRing><coordinates>",
                 _kml_ring(poly.exterior),
                 "</coordinates></LinearRing></outerBoundaryIs>"]
        for hole in poly.interiors:
            parts += ["<innerBoundaryIs><LinearRing><coordinates>",
                      _kml_ring(hole),
                      "</coordinates></LinearRing></innerBoundaryIs>"]
        parts.append("</Polygon>")
        out.append("".join(parts))
    return "".join(out)


def write_kml(path: Path, title: str, levels: dict, concelhos: list,
              min_rcm: int, payload: dict) -> int:
    """Un Placemark por nivel, con los concelhos de ese nivel fusionados.

    Fusionar quita las fronteras internas: menos vertices, fichero mas pequeno
    y un mapa mas legible en marcha. Devuelve el numero de niveles escritos.
    """
    by_level: dict = {}
    for dico, geom in concelhos:
        rcm = levels.get(dico)
        if rcm is None or rcm < min_rcm:
            continue
        by_level.setdefault(rcm, []).append((dico, geom))

    doc = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
           "<name>%s</name>" % title,
           "<description>Risco de incendio IPMA, previsao para %s "
           "(atualizado %s). Nao mostra incendios ativos.</description>"
           % (payload["dataPrev"], payload["fileDate"])]

    for rcm in sorted(RCM_HEX):
        doc.append(
            '<Style id="rcm%d"><LineStyle><color>%s</color><width>2</width></LineStyle>'
            '<PolyStyle><color>%s</color><fill>1</fill><outline>1</outline></PolyStyle></Style>'
            % (rcm, kml_color(RCM_HEX[rcm], 220), kml_color(RCM_HEX[rcm], ALPHA)))

    written = 0
    for rcm in sorted(by_level):
        items = by_level[rcm]
        merged = unary_union([g for _d, g in items])
        if KML_SIMPLIFY > 0:
            merged = merged.simplify(KML_SIMPLIFY, preserve_topology=True)
        if merged.is_empty:
            continue
        doc.append("<Placemark><name>%d - %s (%d concelhos)</name>"
                   "<styleUrl>#rcm%d</styleUrl><MultiGeometry>%s</MultiGeometry></Placemark>"
                   % (rcm, RCM_LABEL[rcm], len(items), rcm, _kml_polygons(merged)))
        written += 1

    doc.append("</Document></kml>")
    path.write_text("".join(doc), encoding="utf-8")
    return written


def main() -> int:
    global ZOOMS
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUTDIR))
    ap.add_argument("--zooms", default="",
                    help="sobrescribe los zooms, p.ej. '6-9' o '6,7,8' (para pruebas)")
    ap.add_argument("--layers", default="today,tomorrow")
    ap.add_argument("--extra-zooms", default="",
                    help="zooms adicionales solo para riesgo alto, p.ej. '13-14'. "
                         "Ahi no se rellenan las teselas vacias, asi que la cuenta "
                         "crece con el area en riesgo, no con el bbox completo.")
    ap.add_argument("--extra-min-rcm", type=int, default=4,
                    help="nivel minimo de rcm que se dibuja en --extra-zooms (por defecto 4)")
    args = ap.parse_args()

    def parse_zooms(text):
        if "-" in text:
            a, b = text.split("-", 1)
            return list(range(int(a), int(b) + 1))
        return [int(v) for v in text.split(",") if v.strip()]

    if args.zooms:
        ZOOMS = parse_zooms(args.zooms)

    specs = [(z, 1, True) for z in ZOOMS]
    extra = parse_zooms(args.extra_zooms) if args.extra_zooms else []
    specs += [(z, args.extra_min_rcm, False) for z in extra]
    specs.sort()
    all_zooms = [z for z, _m, _f in specs]

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    concelhos = load_concelhos()

    day_of = {"today": 0, "tomorrow": 1}
    wanted = [l.strip() for l in args.layers.split(",") if l.strip()]
    for name in wanted:
        if name not in day_of:
            raise SystemExit("[error] capa desconocida: %s" % name)
    data = {}
    for name in wanted:
        data[name] = fetch_rcm(day_of[name])

    t0 = time.time()
    for name, payload in data.items():
        n = build_layer(name, payload["levels"], concelhos, outdir, specs)
        print("[ok] capa %s: %d teselas en total" % (name, n))

    # IPMA regenera los ficheros una vez al dia (~09:35 UTC). Si se ejecuta antes
    # de esa hora, rcm-d0 todavia puede referirse al dia anterior: no es un error,
    # pero se marca para que el visor lo advierta.
    today_utc = datetime.now(timezone.utc).date()
    expected = {"today": today_utc, "tomorrow": today_utc + timedelta(days=1)}

    # Ficheros para apps sin raster propio.
    files_meta = {}

    # KML/KMZ: poligonos con relleno, para apps que si dibujan superficies.
    for name, payload in data.items():
        for suffix, min_rcm in (("", 1), ("-alto", 4)):
            stem = "rcm-%s%s" % (name, suffix)
            kml_path = outdir / (stem + ".kml")
            title = "RCM %s %s(%s)" % (
                name, "nivel 4-5 " if min_rcm > 1 else "", payload["dataPrev"])
            n = write_kml(kml_path, title, payload["levels"], concelhos,
                          min_rcm, payload)
            if n == 0:
                kml_path.unlink(missing_ok=True)
                print("[warn] %s: ningun concelho con rcm >= %d, sin fichero"
                      % (stem, min_rcm), file=sys.stderr)
                continue
            # KMZ = el KML comprimido; DMD2 acepta los dos y pesa mucho menos.
            kmz_path = outdir / (stem + ".kmz")
            with zipfile.ZipFile(kmz_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(kml_path, "doc.kml")
            files_meta["kmz-" + name + suffix] = {
                "kml": kml_path.name, "kmz": kmz_path.name,
                "levels": n, "minRcm": min_rcm,
                "kmlBytes": kml_path.stat().st_size,
                "kmzBytes": kmz_path.stat().st_size,
            }
            print("[ok] %s: %d niveles, KML %.0f KB, KMZ %.0f KB"
                  % (stem, n, kml_path.stat().st_size / 1024,
                     kmz_path.stat().st_size / 1024))

    layers_meta = {}
    for name, payload in data.items():
        want = expected[name].isoformat()
        stale = payload["dataPrev"] != want
        if stale:
            print("[warn] capa %s: IPMA da dataPrev=%s, se esperaba %s "
                  "(publicacion diaria ~09:35 UTC aun no disponible)"
                  % (name, payload["dataPrev"], want), file=sys.stderr)
        layers_meta[name] = {
            "dataPrev": payload["dataPrev"],
            "dataRun": payload["dataRun"],
            "fileDate": payload["fileDate"],
            "concelhos": len(payload["levels"]),
            "expectedDate": want,
            "stale": stale,
        }
    meta = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "zoomMin": min(all_zooms),
        "zoomMax": max(all_zooms),
        # hasta zoomFullMax existen todas las teselas del bbox; por encima solo
        # las de los concelhos con rcm >= extraMinRcm
        "zoomFullMax": max(ZOOMS),
        "extraMinRcm": args.extra_min_rcm if extra else None,
        "bbox": list(BBOX),
        "legend": [{"rcm": k, "label": RCM_LABEL[k], "color": RCM_HEX[k]}
                   for k in sorted(RCM_HEX)],
        "layers": layers_meta,
        "files": files_meta,
    }
    (outdir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    for item in SITE.iterdir():
        target = outdir / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)

    print("[ok] terminado en %.1fs -> %s" % (time.time() - t0, outdir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
