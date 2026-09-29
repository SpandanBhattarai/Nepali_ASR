"""
Concurrency test for the Nepali ASR WebSocket backend.
 
Sends the same recording from several fake users at the same moment and reports
how long each one waited. It also checks whether the server stays responsive to
NEW connections while it is busy transcribing.
 
Usage (from backend/, with the backend already running):
 
    uv run python concurrency_test.py --file debug_audio/<any recording>.webm --clients 5
 
    # through Caddy, from any machine (Caddy uses its own certificate, so --insecure):
    uv run python concurrency_test.py --url wss://192.168.10.61/ws --insecure --file rec.webm --clients 5
 
Get a recording by starting the backend with NEPALI_ASR_DEBUG_AUDIO=1 (see audio_debug.py),
speaking once, and using the .webm/.m4a file it saves in backend/debug_audio/.
"""

import argparse
import asyncio
import json
import ssl
import statistics
import sys
import time
from collections import Counter
 
import websockets
 
DEVANAGARI = "०१२३४५६७८९"


def to_ascii_digits(s: str) -> str:
    return "".join(str(DEVANAGARI.index(c)) if c in DEVANAGARI else c for c in s)


def make_ssl(url: str, insecure: bool):
    if not url.startswith("wss://"):
        return None
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


async def client(idx, url, ctx, audio, rounds, go, out):
    """One user: connect, wait for the starting gun, then send `rounds` recordings one after another."""
    async with websockets.connect(url, ssl=ctx, max_size=None, open_timeout=60) as ws:
        await go.wait()
        for _ in range(rounds):
            t0 = time.perf_counter()
            await ws.send(audio)
            reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=180))
            out.append((idx, time.perf_counter() - t0, reply))


async def probe(url, ctx, stop, samples):
    """While the users above are being served, keep opening NEW connections and time how long each takes."""
    while not stop.is_set():
        t0 = time.perf_counter()
        try:
            async with websockets.connect(url, ssl=ctx, open_timeout=60):
                samples.append(time.perf_counter() - t0)
        except Exception:
            samples.append(float("inf"))
        await asyncio.sleep(0.2)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="ws://127.0.0.1:8000/ws")
    ap.add_argument("--file", required=True, help="a recording (webm / m4a / wav) to send")
    ap.add_argument("--clients", type=int, default=5, help="simultaneous users")
    ap.add_argument("--rounds", type=int, default=1, help="recordings each user sends, one after another")
    ap.add_argument("--insecure", action="store_true", help="skip certificate checks (Caddy 'tls internal')")
    ap.add_argument("--expect", help="expected digits for this recording (e.g. 1253). "
                                      "Checks every reply is correct AND identical, not just fast.")
    args = ap.parse_args()
 
    with open(args.file, "rb") as f:
        audio = f.read()
    ctx = make_ssl(args.url, args.insecure)
    print(f"sending {len(audio)} bytes from {args.clients} user(s) x {args.rounds} round(s) to {args.url}\n")

    # 1) baseline: one user alone
    go = asyncio.Event()
    go.set()
    base = []
    await client(0, args.url, ctx, audio, 1, go, base)
    single = base[0][1]
    print(f"one user alone: {single:.2f}s   reply: {base[0][2]}\n")

    # 2) load: everybody sends at the same moment, plus a probe opening new connections
    go, stop = asyncio.Event(), asyncio.Event()
    results, samples = [], []
    users = [asyncio.create_task(client(i, args.url, ctx, audio, args.rounds, go, results)) for i in range(args.clients)]
    await asyncio.sleep(1.0)                     # let every user connect first
    probe_task = asyncio.create_task(probe(args.url, ctx, stop, samples))
    await asyncio.sleep(0.5)
    t_start = time.perf_counter()
    go.set()
    await asyncio.gather(*users)
    wall = time.perf_counter() - t_start
    stop.set()
    await probe_task
 
    lat = sorted(r[1] for r in results)
    ok = sum(1 for r in results if r[2].get("status") == "success")
    print(f"{args.clients} users at once: {ok}/{len(results)} succeeded, everyone done after {wall:.2f}s")
    print(f"  wait per request: fastest {lat[0]:.2f}s  median {statistics.median(lat):.2f}s  slowest {lat[-1]:.2f}s")
    finite = [s for s in samples if s != float("inf")]
    if finite:
        print(f"  time to open a NEW connection while busy: median {statistics.median(finite):.3f}s  worst {max(finite):.3f}s")
    failed = [r[2] for r in results if r[2].get("status") != "success"]
    if failed:
        print("  first failure:", failed[0])
 
    texts = [r[2].get("text", "") for r in results if r[2].get("status") == "success"]
    counts = Counter(texts)
    print(f"\n  distinct transcripts across {len(texts)} successful replies: {len(counts)}")
    for text, n in counts.most_common():
        print(f"    {n:3d}x  {text!r}")
    if args.expect:
        correct = sum(1 for t in texts if to_ascii_digits(t.strip()) == args.expect)
        print(f"  matching expected value {args.expect!r}: {correct}/{len(texts)} "
              f"({correct / len(texts) * 100:.1f}%)" if texts else "  no successful replies to check")
 
    print("\nreading the numbers")
    serial = wall >= 0.7 * len(results) * single
    print(f"  - requests are handled {'ONE AFTER ANOTHER' if serial else 'partly in parallel'} "
          f"(all {len(results)} took {wall:.1f}s; one alone takes {single:.1f}s).")
    if serial:
        print("    That is expected with one model on one GPU. What matters is how long the LAST user waits.")
    worst = max(finite) if finite else float("inf")
    if worst > max(0.2, 0.4 * single):
        print(f"  - LIKELY PROBLEM: new connections waited up to {worst:.2f}s. The server stops answering "
              "everyone else while it transcribes (the model call blocks the event loop).")
    else:
        print("  - The server stays responsive while it transcribes.")
    if len(counts) > 1:
        print(f"  - INCONSISTENT: the SAME recording produced {len(counts)} different transcripts under load. "
              "This points to shared/leaking state between requests, not microphone or accent issues.")
    elif texts:
        print("  - Consistent: every reply under load was identical.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)