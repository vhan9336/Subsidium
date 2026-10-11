"""Pre-generates the spoken callouts with ElevenLabs, so the demo needs no network.

  export ELEVENLABS_API_KEY=...        (the free tier is enough)
  python tools/make_callouts.py [voice_id]

Writes web/public/audio/<event>.mp3. If a file is missing the dashboard falls back to the
browser's own voice. Keep the lines identical to LINES in web/src/voice.ts.
"""
import json
import os
import pathlib
import sys
import urllib.request

LINES = {
    "cam_lock": "Camera locked on terrain.",
    "terrain_change": "Ground fell away. Camera and rangefinder agree. Correcting the inertial estimate.",
    "rf_fault": "Rangefinder outvoted by camera and inertial. Rangefinder excluded.",
    "cam_fault": "Camera outvoted by inertial and rangefinder. Camera excluded.",
    "rf_dropout": "Rangefinder silent. Cross-checking inertial with the camera.",
    "unresolved": "Sources disagree and can't be isolated. Assuming the closest ground.",
    "cam_abstain": "Camera abstaining. Not enough contrast.",
    "cam_back": "Camera back.",
    "recovered": "All three sources agree again.",
    "rf_back": "Rangefinder back.",
}

key = os.environ.get("ELEVENLABS_API_KEY") or sys.exit("set ELEVENLABS_API_KEY first")
voice = sys.argv[1] if len(sys.argv) > 1 else "JBFqnCBsd6RMkjVDRZzb"      # any voice id from your ElevenLabs library
out = pathlib.Path(__file__).resolve().parent.parent / "web" / "public" / "audio"
out.mkdir(parents=True, exist_ok=True)
for name, text in LINES.items():
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
        data=json.dumps({"text": text, "model_id": "eleven_multilingual_v2"}).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    with urllib.request.urlopen(req) as r:
        (out / f"{name}.mp3").write_bytes(r.read())
    print("wrote", name)
