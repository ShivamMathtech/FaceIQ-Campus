"""Measured CPU inference and matching benchmark. Default frames are synthetic non-face noise."""

from pathlib import Path
import sys, json, time, platform, argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import numpy as np, psutil, cv2
from app.computer_vision.engine import engine, decode_image, normalize, match_embedding

p = argparse.ArgumentParser()
p.add_argument("--frames", type=int, default=60)
p.add_argument("--image", help="Optional consented test image")
p.add_argument("--output", default=str(ROOT / "docs" / "performance-results.json"))
args = p.parse_args()
engine.load()
if not engine.available:
    sys.exit("Models required: " + engine.message)
if args.frames < 10:
    sys.exit("Use at least 10 frames")
rng = np.random.default_rng(42)
frame = (
    decode_image(Path(args.image).read_bytes())[0]
    if args.image
    else rng.integers(35, 220, (480, 640, 3), dtype=np.uint8)
)
for _ in range(5):
    engine.analyze(frame)
if platform.system() == "Linux":
    import resource

    memory_method = "resource maximum RSS; growth is change in process high-water mark"
    memory_mib = lambda: resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
else:
    process = psutil.Process()
    memory_method = "psutil sampled RSS"
    memory_mib = lambda: process.memory_info().rss / 1024**2
cpu_start = time.process_time()
start = time.perf_counter()
latencies = []
faces = []
rss = []
for _ in range(args.frames):
    t = time.perf_counter()
    result = engine.analyze(frame)
    latencies.append((time.perf_counter() - t) * 1000)
    faces.append(len(result))
    rss.append(memory_mib())
elapsed = time.perf_counter() - start
cpu = round(100 * (time.process_time() - cpu_start) / elapsed, 2)
# Execute the real SFace network on a synthetic aligned crop, without claiming a face match.
crop = cv2.resize(frame, (112, 112))
embedding_times = []
for _ in range(args.frames):
    t = time.perf_counter()
    engine.recognizer.feature(crop)
    embedding_times.append((time.perf_counter() - t) * 1000)
vector = normalize(rng.normal(size=128))
matching = {}
for size in (30, 100, 500, 1000):
    gallery = [(str(i), normalize(rng.normal(size=128))) for i in range(size)]
    times = []
    for _ in range(30):
        t = time.perf_counter()
        match_embedding(vector, gallery, 0.55, 0.08)
        times.append((time.perf_counter() - t) * 1000)
    matching[str(size)] = {
        "median_ms": round(float(np.median(times)), 3),
        "p95_ms": round(float(np.percentile(times, 95)), 3),
    }
result = {
    "platform": platform.platform(),
    "python": platform.python_version(),
    "opencv": cv2.__version__,
    "cpu": platform.processor() or platform.machine(),
    "logical_cpus": psutil.cpu_count(),
    "frames": args.frames,
    "input": {
        "kind": (
            "consented user-provided image"
            if args.image
            else "synthetic non-face noise"
        ),
        "width": frame.shape[1],
        "height": frame.shape[0],
    },
    "detected_faces_per_frame": sorted(set(faces)),
    "detection": {
        "wall_seconds": round(elapsed, 3),
        "median_latency_ms": round(float(np.median(latencies)), 3),
        "p95_latency_ms": round(float(np.percentile(latencies, 95)), 3),
        "processed_fps": round(args.frames / elapsed, 2),
        "process_cpu_percent": cpu,
        "memory_measurement": memory_method,
        "rss_peak_mib": round(max(rss), 2),
        "rss_growth_mib": round(rss[-1] - rss[0], 2),
    },
    "sface_synthetic_crop": {
        "median_latency_ms": round(float(np.median(embedding_times)), 3),
        "p95_latency_ms": round(float(np.percentile(embedding_times, 95)), 3),
    },
    "cosine_matching": matching,
    "limitations": [
        "Unthrottled local CPU microbenchmark; not end-to-end webcam FPS.",
        "Synthetic inputs do not establish recognition accuracy, FAR, FRR, liveness or Windows performance.",
        "Process CPU percent may exceed 100% when more than one core is used.",
    ],
}
Path(args.output).parent.mkdir(parents=True, exist_ok=True)
Path(args.output).write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
