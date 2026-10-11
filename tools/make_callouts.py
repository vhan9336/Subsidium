"""Pre-generate the voice callouts with ElevenLabs (no network latency during the demo).

  export ELEVENLABS_API_KEY=...        # free tier is enough
  python tools/make_callouts.py [voice_id]

Writes web/audio/<key>.mp3. The dashboard falls back to the browser voice if a file is missing.
"""
import json
import os
import pathlib
import sys
import urllib.request

LINES = {
    "terrain_change": "Ground came up fast. Camera confirms it. Trusting the rangefinder.",
    "rf_fault": "Rangefinder disagrees with camera and navigation. Rangefinder rejected.",
    "rf_dropout": "Rangefinder lost. Flying on camera and navigation.",
    "disagree": "Sources disagree. Assuming the closest ground.",
    "recovered": "All three sources agree again.",
}

key = os.environ.get("ELEVENLABS_API_KEY") or sys.exit("set ELEVENLABS_API_KEY")
voice = sys.argv[1] if len(sys.argv) > 1 else "JBFqnCBsd6RMkjVDRZzb"   # any voice id from your ElevenLabs library
out = pathlib.Path(__file__).resolve().parent.parent / "web" / "audio"
out.mkdir(parents=True, exist_ok=True)
for name, text in LINES.items():
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
        data=json.dumps({"text": text, "model_id": "eleven_multilingual_v2"}).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    with urllib.request.urlopen(req) as r:
        (out / f"{name}.mp3").write_bytes(r.read())
    print("wrote", name)
