"""Downloads the open footage and maps this project uses.

  python tools/fetch_data.py --list            what there is, and what's already on disk
  python tools/fetch_data.py footage           a whole group (footage or maps)
  python tools/fetch_data.py blue_ghost dart   specific items
  python tools/fetch_data.py texture           cut the moon ground texture out of the LRO map
  python tools/fetch_data.py sites             LRO photos of the four real crash sites (for the replays)
  python tools/fetch_data.py broadcasts        the landing minutes of each mission's own broadcast

NASA media and data are free to use with credit (see data/CATALOG.md). Files go to footage/
and data/, both git-ignored. A download that gets interrupted resumes where it stopped.
"""
from __future__ import annotations

import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
NASA_VIDEO = "https://images-assets.nasa.gov/video/"
PERSEVERANCE = ("JPL-20210222-M2020f-0001-Perseverance%20Rover%E2%80%99s%20Descent%20and%20Touchdown%20on%20Mars/"
                "JPL-20210222-M2020f-0001-Perseverance%20Rover%E2%80%99s%20Descent%20and%20Touchdown%20on%20Mars")
MOON_KIT = "https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/"

# id: (group, destination, MB, url, what it is for)
ITEMS = {
    "blue_ghost": ("footage", "footage/blue_ghost_m1_landing_scalpss.mp4", 12,
                   NASA_VIDEO + "Final_Out_CRF35/Final_Out_CRF35~orig.mp4",
                   "Blue Ghost M1 Moon landing from NASA's SCALPSS cameras, with on-screen altitude labels"),
    "perseverance": ("footage", "footage/perseverance_descent_touchdown_1080p.mp4", 129,
                     NASA_VIDEO + PERSEVERANCE + "~large.mp4",
                     "Perseverance descent and touchdown, onboard cameras (1080p, used by the dashboard)"),
    "dart": ("footage", "footage/dart_impact_replay.mp4", 23,
             "https://svs.gsfc.nasa.gov/vis/a030000/a031100/a031194/dart_impact_replay_1080p25.mp4",
             "DART's DRACO camera approaching Dimorphos until impact"),
    "lro_color_8k": ("maps", "data/lroc_color_poles_8k.tif", 48, MOON_KIT + "lroc_color_poles_8k.tif",
                     "LRO camera global colour mosaic, 8192x4096 (source of the ground texture)"),
}


def fetch(key: str) -> bool:
    _, dest, mb, url, _ = ITEMS[key]
    path = ROOT / dest
    path.parent.mkdir(parents=True, exist_ok=True)
    have = path.stat().st_size if path.exists() else 0
    req = urllib.request.Request(url, headers={"Range": f"bytes={have}-", "User-Agent": "subsidium-fetch"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            if r.status == 200:          # server ignored the range: start over
                have = 0
            total = have + int(r.headers.get("Content-Length", 0))
            with open(path, "ab" if have else "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
                    have += len(chunk)
                    print(f"\r{key}: {have / 1e6:7.1f} / {total / 1e6:.1f} MB", end="", flush=True)
        print()
        return True
    except urllib.error.HTTPError as e:
        if e.code == 416:                # nothing left to fetch
            print(f"{key}: already complete")
            return True
        print(f"{key}: FAILED ({e})")
    except OSError as e:
        print(f"\n{key}: FAILED ({e}); run again to resume")
    return False


def texture() -> bool:
    """Cut a cratered southern-highlands square out of the LRO mosaic for the simulator and 3D view."""
    import cv2

    src = ROOT / ITEMS["lro_color_8k"][1]
    if not src.exists() and not fetch("lro_color_8k"):
        return False
    img = cv2.imread(str(src), cv2.IMREAD_UNCHANGED)
    if img is None:
        print("could not read", src)
        return False
    if img.dtype != "uint8":
        img = (img / 257).astype("uint8")
    h, w = img.shape[:2]
    # longitude 0..35 E, latitude 20..55 S (equirectangular map, longitude -180..180, north up);
    # stays clear of the pole, where this projection smears
    x0, x1, y0, y1 = int(w * 0.5), int(w * (0.5 + 35 / 360)), int(h * 110 / 180), int(h * 145 / 180)
    crop = cv2.resize(img[y0:y1, x0:x1], (1024, 1024), interpolation=cv2.INTER_AREA)
    for dest, args in (("web/public/textures/lro_moon.jpg", [cv2.IMWRITE_JPEG_QUALITY, 88]), ("data/lro_texture.png", [])):
        out = ROOT / dest
        out.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out), crop, args)
        print("wrote", dest)
    return True


LROC = "https://www.lroc.im-ldi.com/ckeditor_assets/pictures/"
# LRO narrow-angle camera images of where each lander actually came down (NASA/GSFC/Arizona State
# University). scenario id: (LROC post, file, annotation to remove: boxes of (x0, y0, x1, y1), crop)
SITES = {
    "hakuto_r_m1": (1302, "1318/content_ispaceImpact_Cover_scale.png",
                    [(340, 342, 756, 364), (340, 734, 756, 756), (340, 342, 362, 756), (734, 342, 756, 756)],
                    (60, 70, 990, 1000)),                      # drop the title and the scale bar
    "resilience": (1456, "1564/content_M1504323448LR_mos.str01.CROP_1300.png", [(552, 552, 640, 640)], None),
    "odysseus_im1": (1360, "1426/content_Nova_C_no_arrow_1100x1100_crop.png", [], None),
    "athena_im2": (1409, "1497/content_M1496181900_LRmos.warp.str01.CROP1300p.png", [], None),
}


def sites() -> bool:
    """Fetch the crash-site images and paint out NASA's arrows and boxes, so the camera tracks
    terrain and not annotation. Originals stay in data/sites/; cleaned copies go to scenarios/sites/."""
    import cv2
    import numpy as np

    ok = True
    for sid, (_, rel, marks, crop) in SITES.items():
        raw = ROOT / "data" / "sites" / f"{sid}.png"
        raw.parent.mkdir(parents=True, exist_ok=True)
        if not raw.exists():
            try:
                urllib.request.urlretrieve(LROC + rel, raw)
            except OSError as e:
                print(f"{sid}: FAILED ({e})")
                ok = False
                continue
        img = cv2.imread(str(raw), cv2.IMREAD_GRAYSCALE)
        mask = np.zeros_like(img)
        for x0, y0, x1, y1 in marks:                 # annotation is drawn in pure white
            mask[y0:y1, x0:x1] = (img[y0:y1, x0:x1] > 225).astype(np.uint8) * 255
        if mask.any():
            img = cv2.inpaint(img, cv2.dilate(mask, np.ones((5, 5), np.uint8)), 5, cv2.INPAINT_TELEA)
        if crop:
            img = img[crop[1]:crop[3], crop[0]:crop[2]]
        out = ROOT / "scenarios" / "sites" / f"{sid}.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        print("wrote", out.relative_to(ROOT))
    return ok


# The landing minutes of each mission's own broadcast: scenario id -> (YouTube id, start s, end s).
# The two ispace streams belong to ispace (Mission 2 is a third-party re-upload of ispace's feed);
# the two IM streams are NASA's official broadcasts. Use with credit; they are never committed.
BROADCASTS = {
    "hakuto_r_m1": ("CpR1UUnix3g", 4060, 4300),
    "resilience": ("CJzo8Dd62o4", 4080, 4330),
    "odysseus_im1": ("Dg2ffigGcYM", 5100, 5340),
    "athena_im2": ("VOPL8nhmQU4", 3560, 3800),
}


def broadcasts() -> bool:
    """Needs two extra packages that are not in requirements.txt: pip install yt-dlp imageio-ffmpeg"""
    import subprocess

    try:
        import imageio_ffmpeg
        import yt_dlp  # noqa: F401
    except ImportError:
        print("broadcasts need: pip install yt-dlp imageio-ffmpeg")
        return False
    ok = True
    for sid, (vid, a, b) in BROADCASTS.items():
        out = ROOT / "footage" / "broadcasts" / f"{sid}.mp4"
        if out.exists():
            print(f"{sid}: already on disk")
            continue
        r = subprocess.run([sys.executable, "-m", "yt_dlp", "-q", "--no-warnings", "--no-part",
                            "--ffmpeg-location", imageio_ffmpeg.get_ffmpeg_exe(),
                            "--download-sections", f"*{a}-{b}", "-f", "136/298/135/134",
                            "-o", str(out), f"https://www.youtube.com/watch?v={vid}"])
        print(f"{sid}: {'ok' if r.returncode == 0 and out.exists() else 'FAILED'}")
        ok &= r.returncode == 0 and out.exists()
    return ok


def main(argv: list[str]) -> int:
    if not argv or "--list" in argv:
        for key, (group, dest, mb, _, why) in ITEMS.items():
            mark = "x" if (ROOT / dest).exists() else " "
            print(f"[{mark}] {key:24s} {group:14s} {mb:6.1f} MB  {why}")
        print("    texture                  (built)                    moon ground texture from lro_color_8k")
        print("    sites                    (built)                    LRO images of the four actual crash sites")
        print("    broadcasts               (yt-dlp)                   landing minutes of each mission's own broadcast")
        return 0
    ok = True
    for a in argv:
        if a in ("texture", "sites", "broadcasts"):
            ok &= {"texture": texture, "sites": sites, "broadcasts": broadcasts}[a]()
            continue
        keys = [k for k, v in ITEMS.items() if a in (k, v[0])]
        if not keys:
            print(f"unknown item or group: {a} (try --list)")
            ok = False
        for k in keys:
            ok &= fetch(k)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
