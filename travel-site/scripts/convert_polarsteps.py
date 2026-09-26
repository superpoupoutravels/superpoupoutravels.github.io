#!/usr/bin/env python3
"""
Convertit un export Polarsteps (dossier "trip") en donnees exploitables
par le site : un JSON par voyage, des photos optimisees en WebP (grande
version + vignette), les videos compressees, et une page HTML statique
par voyage (avec balises de partage correctes pour WhatsApp/Facebook/X).

Usage:
    python3 scripts/convert_polarsteps.py chemin/vers/mon-voyage_12345678

A relancer a chaque nouveau voyage exporte depuis Polarsteps.
Necessite : pip install Pillow  (et, optionnellement, ffmpeg installe sur
la machine pour compresser les videos - sinon elles sont copiees telles quelles).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from PIL import Image, ImageOps

# --- Reglages ---------------------------------------------------------
FULL_MAX_DIMENSION = 1600     # grande version (visionneuse plein ecran)
THUMB_MAX_DIMENSION = 480     # vignette (grille de photos, cartes voyage)
OG_COVER_MAX_DIMENSION = 1200 # image de partage (JPEG, compatibilite max)
WEBP_QUALITY_FULL = 82
WEBP_QUALITY_THUMB = 75
JPEG_QUALITY = 85

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(SITE_ROOT, "data")
TRIPS_DATA_DIR = os.path.join(DATA_DIR, "trips")
PHOTOS_DIR = os.path.join(SITE_ROOT, "photos")
TRIPS_INDEX_PATH = os.path.join(DATA_DIR, "trips.json")
VOYAGES_DIR = os.path.join(SITE_ROOT, "voyages")
TEMPLATE_PATH = os.path.join(SITE_ROOT, "scripts", "templates", "trip_template.html")
INDEX_HTML_PATH = os.path.join(SITE_ROOT, "index.html")
SITE_CONFIG_PATH = os.path.join(SITE_ROOT, "site_config.json")


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text) or "voyage"


def load_site_config():
    default = {"base_url": ""}
    if os.path.isfile(SITE_CONFIG_PATH):
        try:
            with open(SITE_CONFIG_PATH, encoding="utf-8") as f:
                default.update(json.load(f))
        except Exception:
            pass
    return default


def abs_url(base_url, relative_path):
    if not base_url:
        return relative_path
    return base_url.rstrip("/") + "/" + relative_path.lstrip("/")


def ts_to_local_date(ts, tz_name):
    """Convertit un timestamp Polarsteps (UTC) en date locale a l'etape,
    pour eviter qu'une etape prise tard le soir n'affiche le mauvais jour."""
    if not ts:
        return None
    dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
    if tz_name:
        try:
            dt_local = dt_utc.astimezone(ZoneInfo(tz_name))
            return dt_local.strftime("%Y-%m-%d")
        except (ZoneInfoNotFoundError, Exception):
            pass
    return dt_utc.strftime("%Y-%m-%d")


def save_webp_pair(im, dst_full_path, dst_thumb_path):
    os.makedirs(os.path.dirname(dst_full_path), exist_ok=True)
    full = im.copy()
    full.thumbnail((FULL_MAX_DIMENSION, FULL_MAX_DIMENSION), Image.LANCZOS)
    full.save(dst_full_path, "WEBP", quality=WEBP_QUALITY_FULL)

    thumb = im.copy()
    thumb.thumbnail((THUMB_MAX_DIMENSION, THUMB_MAX_DIMENSION), Image.LANCZOS)
    thumb.save(dst_thumb_path, "WEBP", quality=WEBP_QUALITY_THUMB)


def optimize_photo(src_path, dst_full_path, dst_thumb_path):
    try:
        with Image.open(src_path) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            save_webp_pair(im, dst_full_path, dst_thumb_path)
        return True
    except Exception as e:
        print(f"  ! photo ignoree ({src_path}): {e}")
        return False


def make_cover_variants(src_path, trip_slug):
    """Genere la couverture d'un voyage en 3 formats a partir d'une image
    source (locale ou telechargee) : webp plein format, webp vignette,
    et jpeg (pour les balises og:image, mieux supportees par certains
    robots de reseaux sociaux que le webp)."""
    cover_dir_rel = f"{trip_slug}/_cover"
    cover_dir_abs = os.path.join(PHOTOS_DIR, cover_dir_rel)
    os.makedirs(cover_dir_abs, exist_ok=True)
    try:
        with Image.open(src_path) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            full_rel = f"photos/{cover_dir_rel}/cover.webp"
            thumb_rel = f"photos/{cover_dir_rel}/cover_thumb.webp"
            jpg_rel = f"photos/{cover_dir_rel}/cover.jpg"
            save_webp_pair(im, os.path.join(PHOTOS_DIR, cover_dir_rel, "cover.webp"),
                            os.path.join(PHOTOS_DIR, cover_dir_rel, "cover_thumb.webp"))
            jpg = im.copy()
            jpg.thumbnail((OG_COVER_MAX_DIMENSION, OG_COVER_MAX_DIMENSION), Image.LANCZOS)
            jpg.save(os.path.join(PHOTOS_DIR, cover_dir_rel, "cover.jpg"),
                     "JPEG", quality=JPEG_QUALITY, optimize=True)
            return {"full": full_rel, "thumb": thumb_rel, "og": jpg_rel}
    except Exception as e:
        print(f"  ! couverture non generee: {e}")
        return None


def download_to_temp(url):
    try:
        tmp_path = "/tmp/_ps_cover_download.jpg"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp, open(tmp_path, "wb") as out:
            shutil.copyfileobj(resp, out)
        return tmp_path
    except Exception as e:
        print(f"  ! telechargement de la couverture Polarsteps impossible ({e})")
        return None


def compress_video(src_path, dst_path):
    """Compresse une video via ffmpeg si disponible ; sinon copie brute."""
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    if shutil.which("ffmpeg") is None:
        shutil.copyfile(src_path, dst_path)
        print("  ! ffmpeg non installe : video copiee sans compression"
              " (voir README pour l'installer)")
        return
    dst_path_mp4 = os.path.splitext(dst_path)[0] + ".mp4"
    cmd = [
        "ffmpeg", "-y", "-i", src_path,
        "-vf", "scale='min(960,iw)':-2",
        "-c:v", "libx264", "-crf", "28", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart",
        "-loglevel", "error",
        dst_path_mp4,
    ]
    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        print(f"  ! compression video echouee ({e}), copie brute a la place")
        shutil.copyfile(src_path, dst_path)


def find_step_folder(trip_dir, step_id):
    suffix = f"_{step_id}"
    for name in os.listdir(trip_dir):
        full = os.path.join(trip_dir, name)
        if os.path.isdir(full) and name.endswith(suffix):
            return full
    return None


def convert_trip(trip_dir):
    trip_json_path = os.path.join(trip_dir, "trip.json")
    if not os.path.isfile(trip_json_path):
        print(f"Erreur: pas de trip.json dans {trip_dir}")
        sys.exit(1)

    with open(trip_json_path, encoding="utf-8") as f:
        trip = json.load(f)

    config = load_site_config()
    trip_slug = slugify(trip.get("name") or os.path.basename(trip_dir))
    trip_tz = trip.get("timezone_id")
    print(f"Voyage: {trip['name']}  ->  slug: {trip_slug}")

    steps_raw = [s for s in trip.get("all_steps", []) if not s.get("is_deleted")]
    steps_raw.sort(key=lambda s: s.get("start_time") or 0)

    steps_out = []
    total_photos = 0
    first_photo_src = None  # pour la couverture de secours

    for step in steps_raw:
        step_id = step["id"]
        folder = find_step_folder(trip_dir, step_id)
        step_slug = slugify(step.get("display_name") or step.get("name") or str(step_id))
        step_tz = step.get("timezone_id") or trip_tz

        photos_out = []
        videos_out = []
        if folder:
            src_photos_dir = os.path.join(folder, "photos")
            if os.path.isdir(src_photos_dir):
                for i, fname in enumerate(sorted(os.listdir(src_photos_dir))):
                    if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                        continue
                    src = os.path.join(src_photos_dir, fname)
                    if first_photo_src is None:
                        first_photo_src = src
                    base = f"{trip_slug}/{step_slug}-{step_id}/{i:02d}"
                    dst_full = os.path.join(PHOTOS_DIR, f"{base}.webp")
                    dst_thumb = os.path.join(PHOTOS_DIR, f"{base}_thumb.webp")
                    if optimize_photo(src, dst_full, dst_thumb):
                        photos_out.append({
                            "full": f"photos/{base}.webp",
                            "thumb": f"photos/{base}_thumb.webp",
                        })
                        total_photos += 1

            src_videos_dir = os.path.join(folder, "videos")
            if os.path.isdir(src_videos_dir):
                for fname in sorted(os.listdir(src_videos_dir)):
                    if not fname.lower().endswith((".mp4", ".mov")):
                        continue
                    src = os.path.join(src_videos_dir, fname)
                    dst_rel = f"{trip_slug}/{step_slug}-{step_id}/{os.path.splitext(fname)[0]}.mp4"
                    dst_abs = os.path.join(PHOTOS_DIR, dst_rel)
                    if not os.path.exists(dst_abs):
                        print(f"  compression video: {fname}")
                        compress_video(src, dst_abs)
                    videos_out.append(f"photos/{dst_rel}")
        else:
            print(f"  ! aucun dossier trouve pour l'etape '{step.get('name')}' (id {step_id})")

        loc = step.get("location") or {}
        steps_out.append({
            "id": step_id,
            "name": (step.get("display_name") or step.get("name") or "").strip(),
            "description": (step.get("description") or "").strip(),
            "date": ts_to_local_date(step.get("start_time"), step_tz),
            "lat": loc.get("lat"),
            "lon": loc.get("lon"),
            "place": loc.get("detail"),
            "country_code": loc.get("country_code"),
            "weather_condition": step.get("weather_condition"),
            "weather_temperature": step.get("weather_temperature"),
            "photos": photos_out,
            "videos": videos_out,
        })

    # --- Couverture du voyage : priorite a celle choisie sur Polarsteps ---
    cover = None
    remote_cover_url = (
        (trip.get("cover_photo") or {}).get("path")
        or trip.get("cover_photo_path")
    )
    if remote_cover_url:
        print("  telechargement de la couverture Polarsteps...")
        tmp = download_to_temp(remote_cover_url)
        if tmp:
            cover = make_cover_variants(tmp, trip_slug)
            os.remove(tmp)
    if cover is None and first_photo_src:
        print("  couverture de secours : premiere photo disponible")
        cover = make_cover_variants(first_photo_src, trip_slug)

    trip_out = {
        "slug": trip_slug,
        "name": trip.get("name"),
        "summary": trip.get("summary") or "",
        "start_date": ts_to_local_date(trip.get("start_date"), trip_tz),
        "end_date": ts_to_local_date(trip.get("end_date"), trip_tz),
        "total_km": round(trip.get("total_km") or 0),
        "step_count": len(steps_out),
        "photo_count": total_photos,
        "cover": cover,  # {"full":..., "thumb":..., "og":...} ou None
        "countries": sorted({s["country_code"] for s in steps_out if s.get("country_code")}),
        "steps": steps_out,
    }

    os.makedirs(TRIPS_DATA_DIR, exist_ok=True)
    out_path = os.path.join(TRIPS_DATA_DIR, f"{trip_slug}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(trip_out, f, ensure_ascii=False, indent=2)

    print(f"-> {len(steps_out)} etapes, {total_photos} photos optimisees (WebP)")
    print(f"-> {out_path}")

    update_index(trip_out, config)
    generate_trip_page(trip_out, config)


def update_index(trip_out, config):
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.isfile(TRIPS_INDEX_PATH):
        with open(TRIPS_INDEX_PATH, encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = {"trips": []}

    summary = {
        "slug": trip_out["slug"],
        "name": trip_out["name"],
        "summary": trip_out["summary"],
        "start_date": trip_out["start_date"],
        "end_date": trip_out["end_date"],
        "total_km": trip_out["total_km"],
        "step_count": trip_out["step_count"],
        "photo_count": trip_out["photo_count"],
        "cover": trip_out["cover"],
        "countries": trip_out["countries"],
    }

    index["trips"] = [t for t in index["trips"] if t["slug"] != trip_out["slug"]]
    index["trips"].append(summary)
    index["trips"].sort(key=lambda t: t["start_date"] or "", reverse=True)

    with open(TRIPS_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"-> index mis a jour ({TRIPS_INDEX_PATH})")

    update_homepage_meta(index["trips"][0], config)


def fill_template(template, values):
    out = template
    for key, val in values.items():
        out = out.replace(f"{{{{{key}}}}}", val)
    return out


def generate_trip_page(trip_out, config):
    """Genere voyages/<slug>.html : une vraie page statique par voyage,
    avec les bonnes balises og:*, pour que les apercus WhatsApp/Facebook/X
    fonctionnent (ces robots n'executent pas le JavaScript, donc des
    balises injectees en JS ne suffisent pas)."""
    if not os.path.isfile(TEMPLATE_PATH):
        print(f"  ! modele introuvable ({TEMPLATE_PATH}), page statique non generee")
        return

    os.makedirs(VOYAGES_DIR, exist_ok=True)
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        template = f.read()

    page_url = abs_url(config.get("base_url", ""), f"voyages/{trip_out['slug']}.html")
    og_image = abs_url(config.get("base_url", ""), trip_out["cover"]["og"]) if trip_out.get("cover") else ""
    description = trip_out["summary"] or f"{trip_out['step_count']} etapes, {trip_out['total_km']} km."

    if not config.get("base_url"):
        print("  ! site_config.json: base_url est vide -> og:image/og:url resteront"
              " des chemins relatifs, non fiables pour WhatsApp/Facebook/X."
              " Renseigne base_url puis relance le script pour corriger.")

    html = fill_template(template, {
        "SLUG": trip_out["slug"],
        "TITLE": f"{trip_out['name']} — Wayfarer Log",
        "DESCRIPTION": description,
        "OG_IMAGE": og_image,
        "PAGE_URL": page_url,
    })

    out_path = os.path.join(VOYAGES_DIR, f"{trip_out['slug']}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"-> page statique generee ({out_path})")


def update_homepage_meta(latest_trip, config):
    """Met a jour les balises og:* de la page d'accueil pour refleter le
    dernier voyage ajoute (entre les marqueurs <!-- OG:START/END -->)."""
    if not os.path.isfile(INDEX_HTML_PATH):
        return
    with open(INDEX_HTML_PATH, encoding="utf-8") as f:
        html = f.read()

    og_image = abs_url(config.get("base_url", ""), latest_trip["cover"]["og"]) if latest_trip.get("cover") else ""
    description = f"Dernier voyage : {latest_trip['name']}. {latest_trip['summary']}".strip()
    block = f"""<!-- OG:START (regenere automatiquement par convert_polarsteps.py) -->
<meta property="og:title" content="Wayfarer Log">
<meta property="og:description" content="{description}">
<meta property="og:image" content="{og_image}">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image">
<!-- OG:END -->"""

    new_html = re.sub(
        r"<!-- OG:START.*?<!-- OG:END -->",
        block.replace("\\", "\\\\"),
        html,
        flags=re.DOTALL,
    )
    with open(INDEX_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(new_html)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    convert_trip(sys.argv[1])
