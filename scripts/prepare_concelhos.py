"""Genera data/concelhos.geojson a partir de la CAOP (nivel concelho).

Se ejecuta una sola vez (o cuando salga una CAOP nueva). Descarga el GeoJSON
de concelhos de Portugal continental, lo reproyecta de EPSG:3763 (PT-TM06/ETRS89)
a EPSG:4326, simplifica y deja solo los campos DICO y nombre.

    python scripts/prepare_concelhos.py [--source URL_O_FICHERO] [--tolerance 0.001]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests
from pyproj import Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform as shapely_transform

DEFAULT_SOURCE = (
    "https://raw.githubusercontent.com/nmota/caop_GeoJSON/master/"
    "ContinenteConcelhos.geojson"
)
OUT = Path(__file__).resolve().parents[1] / "data" / "concelhos.geojson"


def load_source(source: str) -> dict:
    if source.startswith(("http://", "https://")):
        print(f"[info] descargando {source}")
        r = requests.get(source, timeout=300)
        r.raise_for_status()
        text = r.content.decode("utf-8-sig")
    else:
        text = Path(source).read_text(encoding="utf-8-sig")
    return json.loads(text)


def detect_epsg(fc: dict) -> str:
    name = ((fc.get("crs") or {}).get("properties") or {}).get("name", "")
    if "3763" in name:
        return "EPSG:3763"
    if "3857" in name:
        return "EPSG:3857"
    if "4326" in name or not name:
        return "EPSG:4326"
    # urn:ogc:def:crs:EPSG::XXXX
    code = name.rsplit(":", 1)[-1]
    return f"EPSG:{code}"


def pick(props: dict, *candidates: str) -> str | None:
    lowered = {k.lower(): v for k, v in props.items()}
    for c in candidates:
        if c.lower() in lowered and lowered[c.lower()] not in (None, ""):
            return str(lowered[c.lower()])
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    ap.add_argument("--tolerance", type=float, default=0.001,
                    help="tolerancia de simplificacion en grados")
    args = ap.parse_args()

    fc = load_source(args.source)
    src_epsg = detect_epsg(fc)
    print(f"[info] CRS de origen: {src_epsg}")

    to_wgs84 = None
    if src_epsg != "EPSG:4326":
        tr = Transformer.from_crs(src_epsg, "EPSG:4326", always_xy=True)
        to_wgs84 = lambda x, y, z=None: tr.transform(x, y)  # noqa: E731

    out_features = []
    seen: set[str] = set()
    for feat in fc["features"]:
        props = feat.get("properties") or {}
        dico = pick(props, "DICO", "dico", "COD_MUN", "codigo")
        if not dico:
            print(f"[warn] feature sin DICO: {props}", file=sys.stderr)
            continue
        dico = dico.zfill(4)
        name = pick(props, "Concelho", "concelho", "NAME_2", "municipio", "nome") or ""

        geom = shape(feat["geometry"])
        if to_wgs84 is not None:
            geom = shapely_transform(to_wgs84, geom)
        if args.tolerance > 0:
            geom = geom.simplify(args.tolerance, preserve_topology=True)
        if geom.is_empty:
            print(f"[warn] geometria vacia tras simplificar: {dico}", file=sys.stderr)
            continue
        if not geom.is_valid:
            geom = geom.buffer(0)

        if dico in seen:
            print(f"[warn] DICO duplicado: {dico}", file=sys.stderr)
        seen.add(dico)

        out_features.append({
            "type": "Feature",
            "properties": {"dico": dico, "name": name.title()},
            "geometry": json.loads(json.dumps(mapping(geom))),
        })

    out_features.sort(key=lambda f: f["properties"]["dico"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": out_features},
                  fh, ensure_ascii=False, separators=(",", ":"))

    size_mb = OUT.stat().st_size / 1e6
    print(f"[ok] {len(out_features)} concelhos -> {OUT} ({size_mb:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
