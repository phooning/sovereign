#!/usr/bin/env python3
"""
DEM Download Script
======================
Downloads Digital Elevation Models (DEM) in GeoTIFF format from multiple sources:
  - USGS 3DEP (1/3 arc-second & 1 arc-second)
  - SRTM 30m / SRTM 90m (via OpenTopography or direct NASA/CGIAR)
  - Copernicus DEM GLO-30 (via OpenTopography or AWS Open Data)
  - OpenTopography API (requires free API key for SRTM / COP30)

Requirements:
    pip install requests elevation rasterio numpy click tqdm

Usage examples:
    # Download SRTM 30m DEM for a bounding box
    python dem_dl.py --source srtm30 --bbox -122.5 37.5 -121.5 38.5 --output my_dem.tif

    # Download Copernicus GLO-30 via OpenTopography (needs API key)
    python dem_dl.py --source cop30 --bbox -122.5 37.5 -121.5 38.5 --api-key YOUR_KEY

    # Download USGS 3DEP 1/3 arc-sec
    python dem_dl.py --source usgs --bbox -105.5 39.5 -104.5 40.5 --output usgs_dem.tif

    # List all available sources
    python dem_dl.py --list-sources
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

try:
    import requests
    from tqdm import tqdm
except ImportError:
    print("Installing required packages...")
    os.system("uv add requests tqdm")
    import requests
    from tqdm import tqdm


SOURCES = {
    "srtm30": {
        "name": "SRTM 30m (OpenTopography API)",
        "description": "NASA SRTM ~30m global coverage (56°S–60°N). Requires free API key.",
        "resolution_m": 30,
        "coverage": "Global (56°S–60°N)",
        "requires_api_key": True,
        "provider": "opentopography",
        "demtype": "SRTMGL1",
    },
    "srtm90": {
        "name": "SRTM 90m (OpenTopography API)",
        "description": "NASA SRTM ~90m global coverage. Requires free API key.",
        "resolution_m": 90,
        "coverage": "Global (56°S–60°N)",
        "requires_api_key": True,
        "provider": "opentopography",
        "demtype": "SRTMGL3",
    },
    "cop30": {
        "name": "Copernicus DEM GLO-30 (OpenTopography API)",
        "description": "ESA Copernicus ~30m global DEM. Requires free API key.",
        "resolution_m": 30,
        "coverage": "Global (90°S–90°N)",
        "requires_api_key": True,
        "provider": "opentopography",
        "demtype": "COP30",
    },
    "cop90": {
        "name": "Copernicus DEM GLO-90 (OpenTopography API)",
        "description": "ESA Copernicus ~90m global DEM. Requires free API key.",
        "resolution_m": 90,
        "coverage": "Global (90°S–90°N)",
        "requires_api_key": True,
        "provider": "opentopography",
        "demtype": "COP90",
    },
    "alos": {
        "name": "ALOS World 3D 30m (OpenTopography API)",
        "description": "JAXA ALOS AW3D30 ~30m DEM. Requires free API key.",
        "resolution_m": 30,
        "coverage": "Global (82°S–85°N)",
        "requires_api_key": True,
        "provider": "opentopography",
        "demtype": "AW3D30",
    },
    "usgs": {
        "name": "USGS 3DEP 1/3 arc-second (~10m)",
        "description": "USGS 3D Elevation Program, best coverage for CONUS.",
        "resolution_m": 10,
        "coverage": "CONUS + territories",
        "requires_api_key": False,
        "provider": "usgs",
    },
    "usgs1": {
        "name": "USGS 3DEP 1 arc-second (~30m)",
        "description": "USGS 3D Elevation Program 1 arc-second, CONUS + some global.",
        "resolution_m": 30,
        "coverage": "CONUS + territories",
        "requires_api_key": False,
        "provider": "usgs",
    },
    "cop30_aws": {
        "name": "Copernicus DEM GLO-30 (AWS Open Data – no key needed)",
        "description": "Copernicus 30m tiles fetched directly from AWS S3 public bucket.",
        "resolution_m": 30,
        "coverage": "Global",
        "requires_api_key": False,
        "provider": "aws_cop30",
    },
}

# OpenTopography REST API endpoint
OPENTOPO_API = "https://portal.opentopography.org/API/globaldem"

# USGS TNM (The National Map) API
USGS_TNM_API = "https://tnmaccess.nationalmap.gov/api/v1/products"
USGS_DOWNLOAD_API = "https://tnmaccess.nationalmap.gov/api/v1/downloads"

# AWS Copernicus GLO-30 public bucket
AWS_COP30_BASE = "https://copernicus-dem-30m.s3.amazonaws.com"


def bbox_str(west, south, east, north):
    return f"W{abs(west):.4f} S{abs(south):.4f} E{abs(east):.4f} N{abs(north):.4f}"


def download_file(url, dest_path, desc="Downloading", headers=None, params=None):
    """Stream-download a file with a tqdm progress bar."""
    resp = requests.get(
        url, headers=headers or {}, params=params or {}, stream=True, timeout=120
    )
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    with (
        open(dest_path, "wb") as fh,
        tqdm(
            desc=desc, total=total, unit="B", unit_scale=True, unit_divisor=1024
        ) as bar,
    ):
        for chunk in resp.iter_content(chunk_size=8192):
            fh.write(chunk)
            bar.update(len(chunk))

    return dest_path


# ---------------------------------------------------------------------------
# Provider: OpenTopography
# ---------------------------------------------------------------------------


def fetch_opentopography(demtype, west, south, east, north, api_key, output_path):
    """Download a DEM via the OpenTopography Global DEM API."""
    print(
        f"\n[OpenTopography] Requesting {demtype} for bbox "
        f"({west},{south}) -> ({east},{north}) ..."
    )

    params = {
        "demtype": demtype,
        "west": west,
        "south": south,
        "east": east,
        "north": north,
        "outputFormat": "GTiff",
        "API_Key": api_key,
    }

    resp = requests.get(OPENTOPO_API, params=params, stream=True, timeout=300)

    # Check for API errors returned as JSON
    content_type = resp.headers.get("Content-Type", "")
    if "application/json" in content_type or resp.status_code != 200:
        try:
            err = resp.json()
            print(f"[ERROR] OpenTopography API error: {err}")
        except Exception:
            print(f"[ERROR] HTTP {resp.status_code}: {resp.text[:400]}")
        sys.exit(1)

    total = int(resp.headers.get("content-length", 0))
    with (
        open(output_path, "wb") as fh,
        tqdm(desc="Downloading GeoTIFF", total=total, unit="B", unit_scale=True) as bar,
    ):
        for chunk in resp.iter_content(chunk_size=8192):
            fh.write(chunk)
            bar.update(len(chunk))

    print(f"[OK] Saved to: {output_path}")
    _print_tif_info(output_path)


# ---------------------------------------------------------------------------
# Provider: USGS TNM
# ---------------------------------------------------------------------------

USGS_DATASET_TAGS = {
    "usgs": "National Elevation Dataset (NED) 1/3 arc-second",
    "usgs1": "National Elevation Dataset (NED) 1 arc-second",
}

USGS_PRODFORMAT = "GeoTIFF"


def fetch_usgs(source_key, west, south, east, north, output_path):
    """Download USGS 3DEP tiles via The National Map API."""
    dataset = USGS_DATASET_TAGS[source_key]
    print(
        f"\n[USGS TNM] Querying '{dataset}' for "
        f"bbox ({west},{south}) -> ({east},{north}) ..."
    )

    params = {
        "datasets": dataset,
        "bbox": f"{west},{south},{east},{north}",
        "prodFormats": USGS_PRODFORMAT,
        "outputFormat": "JSON",
        "max": 50,
        "offset": 0,
    }

    resp = requests.get(USGS_TNM_API, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    items = data.get("items", [])
    if not items:
        print("[WARN] No USGS tiles found for this bbox/dataset.")
        print("       Try a smaller area, a different dataset, or check coverage at:")
        print("       https://apps.nationalmap.gov/downloader/")
        sys.exit(1)

    print(f"  Found {len(items)} tile(s).")

    tile_paths = []
    tmp_dir = Path(tempfile.mkdtemp(prefix="usgs_dem_"))

    for i, item in enumerate(items, 1):
        # Find the GeoTIFF download URL
        dl_url = None
        for link in item.get("downloadURLs", {}).values():
            if link.endswith(".tif") or link.endswith(".img"):
                dl_url = link
                break
        if not dl_url:
            # Fallback: try the main download URL
            dl_url = item.get("downloadURL", "")

        if not dl_url:
            print(f"  [SKIP] No download URL for tile {i}: {item.get('title', '?')}")
            continue

        tile_file = tmp_dir / f"tile_{i:03d}.tif"
        print(f"  [{i}/{len(items)}] {item.get('title', 'tile')}")
        download_file(dl_url, tile_file, desc=f"  Tile {i}")
        tile_paths.append(str(tile_file))

    if not tile_paths:
        print("[ERROR] No tiles downloaded.")
        sys.exit(1)

    if len(tile_paths) == 1:
        import shutil

        shutil.move(tile_paths[0], output_path)
    else:
        _merge_tifs(tile_paths, output_path)

    print(f"[OK] Saved to: {output_path}")
    _print_tif_info(output_path)


# ---------------------------------------------------------------------------
# Provider: AWS Copernicus GLO-30 (no API key)
# ---------------------------------------------------------------------------


def _cop30_tile_name(lat, lon):
    """Return the Copernicus GLO-30 tile name for a given 1°x1° cell."""
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"Copernicus_DSM_COG_10_{ns}{abs(lat):02d}_00_{ew}{abs(lon):03d}_00_DEM"


def fetch_aws_cop30(west, south, east, north, output_path):
    """Download Copernicus GLO-30 tiles from the AWS public S3 bucket."""
    import math

    print(
        f"\n[AWS COP30] Fetching Copernicus GLO-30 tiles for "
        f"bbox ({west},{south}) -> ({east},{north}) ..."
    )

    lat_range = range(int(math.floor(south)), int(math.ceil(north)))
    lon_range = range(int(math.floor(west)), int(math.ceil(east)))

    tile_paths = []
    tmp_dir = Path(tempfile.mkdtemp(prefix="cop30_"))

    for lat in lat_range:
        for lon in lon_range:
            tile_name = _cop30_tile_name(lat, lon)
            url = f"{AWS_COP30_BASE}/{tile_name}/{tile_name}.tif"
            tile_file = tmp_dir / f"{tile_name}.tif"

            print(f"  Tile: {tile_name}")
            try:
                download_file(url, tile_file, desc="  Download")
                tile_paths.append(str(tile_file))
            except requests.HTTPError as e:
                print(f"  [SKIP] {e} — tile may not exist (ocean/no data)")

    if not tile_paths:
        print("[ERROR] No COP30 tiles found. Check bbox or try OpenTopography.")
        sys.exit(1)

    if len(tile_paths) == 1:
        import shutil

        shutil.move(tile_paths[0], output_path)
    else:
        _merge_tifs(tile_paths, output_path)

    print(f"[OK] Saved to: {output_path}")
    _print_tif_info(output_path)


# ---------------------------------------------------------------------------
# GeoTIFF utilities
# ---------------------------------------------------------------------------


def _merge_tifs(tile_paths, output_path):
    """Merge multiple GeoTIFF tiles into one using gdal_merge or rasterio."""
    print(f"\n  Merging {len(tile_paths)} tiles -> {output_path} ...")

    # Try GDAL first (usually fastest)
    gdal_merge = _find_gdal_merge()
    if gdal_merge:
        tiles_str = " ".join(f'"{p}"' for p in tile_paths)
        cmd = f'{gdal_merge} -o "{output_path}" -of GTiff {tiles_str}'
        ret = os.system(cmd)
        if ret == 0:
            return

    # Fallback: rasterio
    try:
        import rasterio
        from rasterio.merge import merge as rio_merge

        datasets = [rasterio.open(p) for p in tile_paths]
        mosaic, transform = rio_merge(datasets)
        meta = datasets[0].meta.copy()
        meta.update(
            {
                "driver": "GTiff",
                "height": mosaic.shape[1],
                "width": mosaic.shape[2],
                "transform": transform,
                "compress": "lzw",
            }
        )
        with rasterio.open(output_path, "w", **meta) as dst:
            dst.write(mosaic)
        for ds in datasets:
            ds.close()
        return
    except ImportError:
        pass

    print("[ERROR] Cannot merge tiles: install rasterio or gdal.")
    sys.exit(1)


def _find_gdal_merge():
    import shutil

    for name in ("gdal_merge.py", "gdal_merge"):
        path = shutil.which(name)
        if path:
            return f"python {path}" if name.endswith(".py") else path
    return None


def _print_tif_info(path):
    """Print basic info about the GeoTIFF if rasterio is available."""
    try:
        import rasterio

        with rasterio.open(path) as ds:
            print("\n  ── GeoTIFF Info ──────────────────────────────")
            print(f"  File   : {path}")
            print(f"  Size   : {ds.width} x {ds.height} px")
            print(f"  CRS    : {ds.crs}")
            b = ds.bounds
            print(
                f"  Bounds : ({b.left:.5f}, {b.bottom:.5f}) -> "
                f"({b.right:.5f}, {b.top:.5f})"
            )
            print(f"  Bands  : {ds.count}  |  dtype: {ds.dtypes[0]}")
            sz = Path(path).stat().st_size / (1024 * 1024)
            print(f"  Size   : {sz:.2f} MB")
            print("  ──────────────────────────────────────────────\n")
    except ImportError:
        sz = Path(path).stat().st_size / (1024 * 1024)
        print(f"\n  Output file: {path}  ({sz:.2f} MB)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def list_sources():
    print("\nAvailable DEM Sources")
    print("=" * 68)
    for key, info in SOURCES.items():
        key_req = (
            " [API key required]" if info["requires_api_key"] else " [no key needed]"
        )
        print(f"\n  --source {key:<10}{key_req}")
        print(f"    {info['name']}")
        print(f"    Resolution : ~{info['resolution_m']} m")
        print(f"    Coverage   : {info['coverage']}")
        print(f"    {info['description']}")
    print()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download DEM GeoTIFFs from USGS, SRTM, Copernicus, or OpenTopography.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--source",
        default="srtm30",
        choices=list(SOURCES.keys()),
        help="DEM source (default: srtm30)",
    )
    parser.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        help="Bounding box in decimal degrees (WGS84)",
    )
    parser.add_argument(
        "--output", default=None, help="Output GeoTIFF path (auto-named if omitted)"
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenTopography API key (or set env OPENTOPO_API_KEY)",
    )
    parser.add_argument(
        "--list-sources", action="store_true", help="Print available sources and exit"
    )
    return parser.parse_args()


def dem_dl():
    args = parse_args()

    if args.list_sources:
        list_sources()
        sys.exit(0)

    if not args.bbox:
        print("[ERROR] --bbox WEST SOUTH EAST NORTH is required.\n")
        print(
            "Example: python dem_dl.py --source srtm30 --bbox -122.5 37.5 -121.5 38.5\n"
        )
        sys.exit(1)

    west, south, east, north = args.bbox

    # Validate bbox
    assert -180 <= west < east <= 180, "Invalid longitude range"
    assert -90 <= south < north <= 90, "Invalid latitude range"

    source_info = SOURCES[args.source]
    output_path = args.output or (
        f"dem_{args.source}_{west:.2f}_{south:.2f}_{east:.2f}_{north:.2f}.tif".replace(
            "-", "m"
        )
    )

    print("=" * 60)
    print("  DEM Download")
    print("=" * 60)
    print(f"  Source  : {source_info['name']}")
    print(f"  BBox    : {bbox_str(west, south, east, north)}")
    print(f"  Output  : {output_path}")
    print("=" * 60)

    provider = source_info["provider"]

    # ── OpenTopography ──────────────────────────────────────────────────────
    if provider == "opentopography":
        api_key = args.api_key or os.environ.get("OPENTOPO_API_KEY", "")
        if not api_key:
            print("\n[ERROR] This source requires an OpenTopography API key.")
            print("  1. Register for free at https://portal.opentopography.org/")
            print("  2. Pass it with --api-key YOUR_KEY")
            print(
                "     or set the environment variable: export OPENTOPO_API_KEY=YOUR_KEY\n"
            )
            sys.exit(1)
        fetch_opentopography(
            source_info["demtype"], west, south, east, north, api_key, output_path
        )

    # ── USGS TNM ────────────────────────────────────────────────────────────
    elif provider == "usgs":
        fetch_usgs(args.source, west, south, east, north, output_path)

    # ── AWS Copernicus GLO-30 (no key) ──────────────────────────────────────
    elif provider == "aws_cop30":
        fetch_aws_cop30(west, south, east, north, output_path)

    else:
        print(f"[ERROR] Unknown provider: {provider}")
        sys.exit(1)
