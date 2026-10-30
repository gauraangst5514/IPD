"""Project-local setup, readiness checks and three-service development launcher.

python3 scripts/dev.py doctor
python3 scripts/dev.py setup [--with-vision]
python3 scripts/dev.py start
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "var"
PYTHON = ROOT / ".venv" / "bin" / "python"
MODULES = ["fastapi", "uvicorn", "sqlalchemy", "greenlet", "aiosqlite", "pydantic_settings",
           "httpx", "multipart", "jose", "bcrypt", "email_validator", "boto3",
           "reportlab", "PIL", "numpy", "imagehash", "exifread"]
VISION_MODULES = ["torch", "torchvision", "ultralytics", "cv2", "timm"]


def environment():
    RUNTIME.mkdir(exist_ok=True)
    secret_file = RUNTIME / "dev.secret"
    if not secret_file.exists():
        with secret_file.open("x") as output:
            output.write(secrets.token_urlsafe(48))
        secret_file.chmod(0o600)
    env = dict(os.environ)
    env.setdefault("NO_PROXY", "127.0.0.1,localhost")
    env.setdefault("OMP_NUM_THREADS", "4")
    env.setdefault("MKL_NUM_THREADS", "4")
    env.setdefault("RETRIEVAL_DAMAGE_EVIDENCE", "1")
    env.setdefault("DATABASE_URL", "sqlite+aiosqlite:///" + str(RUNTIME / "intelliclaim.sqlite3"))
    env.setdefault("SECRET_KEY", secret_file.read_text().strip())
    env.setdefault("STORAGE_BACKEND", "local")
    env.setdefault("UPLOADS_DIR", str(RUNTIME / "uploads"))
    env.setdefault("PROCESSING_MODE", "inline")
    env.setdefault("BACKEND_PORT", "8010")
    env.setdefault("ML_PORT", "8011")
    env.setdefault("FRONTEND_PORT", "5183")
    env.setdefault("ML_SERVICE_URL", "http://127.0.0.1:" + env["ML_PORT"])
    env.setdefault("DEBUG", "false")
    if "RETRIEVAL_GALLERY" not in env:
        from prepare_demo_gallery import prepare
        env["RETRIEVAL_GALLERY"] = str(prepare())
    env.setdefault("IMAGE_HISTORY_PATH", str(RUNTIME / "image_history.sqlite3"))
    env.setdefault("UV_CACHE_DIR", str(RUNTIME / "uv-cache"))
    env.setdefault("UV_PYTHON_INSTALL_DIR", str(RUNTIME / "python"))
    env.setdefault("YOLO_CONFIG_DIR", str(RUNTIME / "yolo-config"))
    env.setdefault("MPLCONFIGDIR", str(RUNTIME / "matplotlib"))
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "backend"), str(ROOT)])
    return env


def doctor():
    python = str(PYTHON if PYTHON.exists() else Path(sys.executable))
    code = ("import json,sys,importlib.util; "
            f"print(json.dumps({{'version':list(sys.version_info[:2]),'missing':[m for m in {MODULES!r} if importlib.util.find_spec(m) is None], 'vision_missing':[m for m in {VISION_MODULES!r} if importlib.util.find_spec(m) is None]}}))")
    report = json.loads(subprocess.check_output([python, "-c", code], text=True))
    candidates = [os.environ["DAMAGE_MODEL_PATH"]] if os.environ.get("DAMAGE_MODEL_PATH") else [
        "ml/weights/detection/cardd_yolov8_v2/weights/best.pt",
        "ml/weights/detection/cardd_yolov8/weights/best.pt"]
    checkpoint = next((str(p) for raw in candidates
                       for p in [Path(raw) if Path(raw).is_absolute() else ROOT / raw] if p.is_file()), None)
    blockers = []
    if report["version"] != [3, 11]:
        blockers.append("Python 3.11 project environment is not available")
    if report["missing"]:
        blockers.append("Missing Python packages: " + ", ".join(report["missing"]))
    if not shutil.which("npm"):
        blockers.append("Node.js/npm is not available")
    elif not (ROOT / "frontend" / "node_modules" / ".bin" / "vite").exists():
        blockers.append("Frontend packages are not installed")
    notes = []
    if not checkpoint:
        notes.append("Damage, severity and cost remain unavailable until a compatible trained CarDD checkpoint and vision packages are supplied.")
    elif report["vision_missing"]:
        notes.append("Damage checkpoint found, but vision packages are missing: " + ", ".join(report["vision_missing"]) + ". Run setup --with-vision.")
    return {"ready_to_start": not blockers, "python": python,
            "python_version": ".".join(map(str, report["version"])), "blockers": blockers,
            "damage_checkpoint_found": bool(checkpoint),
            "vision_packages_missing": report["vision_missing"],
            "notes": notes}


def run(args, **kwargs):
    subprocess.run(args, check=True, cwd=ROOT, **kwargs)


def setup(with_vision=False):
    env = environment()
    uv = shutil.which("uv")
    if not PYTHON.exists():
        available = shutil.which("python3.11")
        if available:
            run([available, "-m", "venv", str(ROOT / ".venv")], env=env)
        elif sys.version_info[:2] == (3, 11):
            run([sys.executable, "-m", "venv", str(ROOT / ".venv")], env=env)
        elif uv:
            run([uv, "venv", "--python", "3.11", str(ROOT / ".venv")], env=env)
        else:
            raise RuntimeError("Install Python 3.11 or uv, then rerun setup")
    requirement = "requirements-vision.txt" if with_vision else "requirements-dev.txt"
    if uv:
        run([uv, "pip", "install", "--python", str(PYTHON), "-r", requirement], env=env)
    else:
        run([str(PYTHON), "-m", "pip", "install", "-r", requirement], env=env)
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("Install Node.js 20 or newer before setting up the frontend")
    subprocess.run([npm, "ci", "--cache", str(RUNTIME / "npm-cache")],
                   cwd=ROOT / "frontend", env=env, check=True)
    run([str(PYTHON), "scripts/seed_demo.py"], env=env)
    run([str(PYTHON), "scripts/train_tabular.py"], env=env)
    if with_vision:
        run([str(PYTHON), "scripts/train_graph.py"], env=env)
    print("Setup completed. Run: python3 scripts/dev.py start")


def start():
    report = doctor()
    if not report["ready_to_start"]:
        print(json.dumps(report, indent=2))
        raise RuntimeError("Resolve the blockers above with scripts/dev.py setup")
    env = environment()
    run([str(PYTHON), "scripts/seed_demo.py"], env=env)
    processes = []
    logs = []
    commands = [
        ("ml", [str(PYTHON), "-m", "uvicorn", "ml.serve:app", "--host", "127.0.0.1", "--port", env["ML_PORT"]], ROOT),
        ("backend", [str(PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", env["BACKEND_PORT"]], ROOT),
        ("frontend", [shutil.which("npm"), "run", "dev", "--", "--host", "127.0.0.1", "--strictPort", "--port", env["FRONTEND_PORT"]], ROOT / "frontend"),
    ]
    try:
        for name, command, cwd in commands:
            log = (RUNTIME / (name + ".log")).open("a")
            logs.append(log)
            processes.append(subprocess.Popen(command, cwd=cwd, env=env,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True))
        print("Starting IntelliClaim: http://127.0.0.1:" + env["FRONTEND_PORT"], flush=True)
        print("Logs and generated demo login credentials are in var/.", flush=True)
        if report["notes"]:
            print(report["notes"][0], flush=True)
        while True:
            for (name, _, _), process in zip(commands, processes):
                if process.poll() is not None:
                    raise RuntimeError(f"{name} stopped. Read var/{name}.log")
            time.sleep(0.5)
    finally:
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        for log in logs:
            log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["doctor", "setup", "start", "seed", "backfill", "status", "stop", "validate"])
    parser.add_argument("--with-vision", action="store_true")
    parser.add_argument("--full-stack", action="store_true")
    args = parser.parse_args()
    try:
        if args.full_stack:
            if args.command not in {"start","status","stop","validate"}:
                raise RuntimeError("Full stack supports start, status, stop and validate")
            import full_stack
            full_stack.main(args.command)
            return 0
        if args.command == "doctor":
            report = doctor()
            print(json.dumps(report, indent=2))
            return 0 if report["ready_to_start"] else 1
        if args.command == "setup":
            setup(args.with_vision)
        elif args.command == "seed":
            run([str(PYTHON), "scripts/seed_demo.py"], env=environment())
        elif args.command == "backfill":
            run([str(PYTHON), "scripts/backfill_image_history.py"], env=environment())
        else:
            start()
        return 0
    except KeyboardInterrupt:
        return 0
    except (RuntimeError, subprocess.CalledProcessError, FileNotFoundError) as error:
        print(f"Could not complete {args.command}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
