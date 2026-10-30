"""Full infrastructure launcher, isolated from the lightweight SQLite mode."""
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/"var"

def env_file():
    RUNTIME.mkdir(exist_ok=True)
    path=RUNTIME/"full-stack.env"
    if not path.exists():
        values={"POSTGRES_PASSWORD":secrets.token_urlsafe(24),"NEO4J_PASSWORD":secrets.token_urlsafe(24),
                "MINIO_USER":"intelliclaim","MINIO_PASSWORD":secrets.token_urlsafe(24),
                "SECRET_KEY":secrets.token_urlsafe(48),"S3_PUBLIC_ENDPOINT":"http://localhost:9000"}
        with path.open("x") as output:
            output.write("".join(key+"="+value+"\n" for key,value in values.items()))
        path.chmod(0o600)
    return path

def command():
    if not shutil.which("docker"):raise RuntimeError("Install/start Docker Desktop first")
    args=["docker","compose","-p",os.environ.get("INTELLICLAIM_COMPOSE_PROJECT", "intelliclaim-gauraang"),"--env-file",str(env_file()),
          "-f",str(ROOT/"docker-compose.yml")]
    if os.environ.get("INTELLICLAIM_COMPOSE_OVERRIDE"):
        args += ["-f", os.environ["INTELLICLAIM_COMPOSE_OVERRIDE"]]
    return args

def run(args):
    subprocess.run(args,cwd=ROOT,check=True)

def main(action="start"):
    compose=command()
    run(compose+["config","--quiet"])
    if action=="validate":
        print("Compose configuration is valid. This does not establish service readiness.")
        return
    if action=="status":
        run(compose+["ps"]);return
    if action=="stop":
        run(compose+["stop"]);return
    # A denied Docker connection is a hard boundary; never start a partial stack.
    try:
        probe=subprocess.run(["docker","info","--format","{{.ServerVersion}}"],cwd=ROOT,
                              capture_output=True,text=True,timeout=15)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Docker daemon did not respond; start Docker Desktop and retry")
    if probe.returncode:
        raise RuntimeError("Docker daemon unavailable to this session. "+probe.stderr.strip())
    if not (ROOT/"ml/weights/detection/cardd_yolov8/weights/best.pt").is_file():
        raise RuntimeError("Supply the trusted CarDD checkpoint before starting the full stack")
    for filename in ["model.json","graph.json"]:
        if not (ROOT/"ml/weights/tabular"/filename).is_file():
            raise RuntimeError("Train the structured research models before starting: missing "+filename)
    run(compose+["up","--build","--detach","--wait","--wait-timeout","300"])
    run(compose+["exec","-T","backend","python","-m","scripts.seed_demo"])
    destination=RUNTIME/"full-stack-accounts.json"
    run(compose+["cp","backend:/app/var/demo_accounts.json",str(destination)])
    destination.chmod(0o600)
    print("Full stack started: http://localhost:5173")
    print("Demo accounts: var/full-stack-accounts.json")
    print("The dashboard reports actual services and available/missing models.")
    print("Missing trained model artifacts remain unavailable; they are not implied by container readiness.")

if __name__=="__main__":
    import sys
    main(sys.argv[1] if len(sys.argv)>1 else "start")
