"""
Parsing accuracy test for the Nepali ASR backend.
 
Reads a folder of test clips (e.g. the ones you generated with ElevenLabs),
sends each one to the backend once, and checks the transcript against the
expected number encoded in the file name.
 
File naming convention (case-insensitive extension, any of .mp3/.wav/.m4a/.webm):
 
    <label>_<expected-digits>.<ext>
 
    num_1253.mp3        -> expected "1253"
    digits_0123.mp3      -> expected "0123"   (leading zero kept)
    en_4444.mp3          -> expected "4444"
 
Everything after the LAST underscore and before the extension must be the
expected digits (ASCII 0-9 only). Files that don't match this pattern are
skipped with a warning, not silently ignored.
 
Usage (from backend/, with the backend already running):
 
    uv run python accuracy_test.py --dir eleven_clips
    uv run python accuracy_test.py --dir eleven_clips --url wss://192.168.10.61/ws --insecure
    uv run python accuracy_test.py --dir eleven_clips --csv results.csv
"""

import argparse
import asyncio
import csv
import json
import re
import ssl
import sys
import time
from pathlib import Path
 
import websockets
 
DEVANAGARI = "०१२३४५६७८९"
NAME_RE = re.compile(r"_([0-9]+)\.[A-Za-z0-9]+$")
 
 
def to_ascii_digits(s: str) -> str:
    return "".join(str(DEVANAGARI.index(c)) if c in DEVANAGARI else c for c in s)
 
 
def expected_from_filename(path: Path) -> str | None:
    m = NAME_RE.search(path.name)
    return m.group(1) if m else None
 
 
def make_ssl(url: str, insecure: bool):
    if not url.startswith("wss://"):
        return None
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx
 
 
async def send_one(ws, audio: bytes, timeout: float):
    t0 = time.perf_counter()
    await ws.send(audio)
    reply = json.loads(await asyncio.wait_for(ws.recv(), timeout))
    return time.perf_counter() - t0, reply
 
 
async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, help="folder of test clips")
    ap.add_argument("--url", default="ws://127.0.0.1:8000/ws")
    ap.add_argument("--insecure", action="store_true", help="skip certificate checks (Caddy 'tls internal')")
    ap.add_argument("--timeout", type=float, default=60, help="seconds to wait for each reply")
    ap.add_argument("--csv", help="also write the per-file results to this CSV file")
    args = ap.parse_args()
    results = []  # defined up front so it always exists, even if nothing gets tested below
 
    folder = Path(args.dir)
    if not folder.is_dir():
        sys.exit(f"Not a folder: {folder}")
 
    exts = {".mp3", ".wav", ".m4a", ".webm", ".ogg"}
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in exts)
    if not files:
        sys.exit(f"No audio files ({', '.join(sorted(exts))}) found in {folder}")
 
    rows = []
    skipped = []
    for p in files:
        expected = expected_from_filename(p)
        if expected is None:
            skipped.append(p.name)
            continue
        rows.append((p, expected))
 
    if skipped:
        print(f"skipping {len(skipped)} file(s) with no _<digits> in the name: {', '.join(skipped)}")
    if not rows:
        sys.exit("Nothing left to test after skipping unnamed files.")
 
    print(f"testing {len(rows)} file(s) against {args.url}\n")
 
    ctx = make_ssl(args.url, args.insecure)
    async with websockets.connect(args.url, ssl=ctx, max_size=None, open_timeout=60) as ws:
        for p, expected in rows:
            audio = p.read_bytes()
            try:
                latency, reply = await send_one(ws, audio, args.timeout)
            except asyncio.TimeoutError:
                results.append((p.name, expected, None, "TIMEOUT", None))
                print(f"{p.name:28} expected {expected:>8}   TIMEOUT")
                continue
 
            if reply.get("status") != "success":
                got_display = f"ERROR: {reply.get('message')}"
                got_ascii = None
            else:
                text = reply.get("text", "")
                got_ascii = to_ascii_digits(text.strip())
                got_display = text
 
            verdict = (
                "MATCH" if got_ascii == expected
                else "no-digits" if got_ascii is not None and not got_ascii.isdigit()
                else "MISMATCH"
            )
            results.append((p.name, expected, got_ascii, verdict, latency))
            mark = "OK  " if verdict == "MATCH" else "FAIL"
            print(f"{mark} {p.name:28} expected {expected:>8}   got {got_display!r:20} ({verdict})")
 
    total = len(results)
    matched = sum(1 for r in results if r[3] == "MATCH")
    timeouts = sum(1 for r in results if r[3] == "TIMEOUT")
    errors = sum(1 for r in results if isinstance(r[2], type(None)) and r[3] not in ("TIMEOUT",))
 
    print(f"\n{matched}/{total} correct ({matched / total * 100:.1f}%)")
    if timeouts:
        print(f"{timeouts} timed out")
    mismatches = [r for r in results if r[3] not in ("MATCH", "TIMEOUT")]
    if mismatches:
        print("\nmismatches / failures:")
        for name, expected, got, verdict, _ in mismatches:
            print(f"  {name}: expected {expected}, got {got!r} ({verdict})")
 
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["file", "expected", "got", "verdict", "latency_s"])
            for name, expected, got, verdict, latency in results:
                w.writerow([name, expected, got, verdict, f"{latency:.3f}" if latency else ""])
        print(f"\nwrote {args.csv}")
 
 
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)
 