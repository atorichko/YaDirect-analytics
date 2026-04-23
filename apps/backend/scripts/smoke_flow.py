"""End-to-end smoke flow: login -> list accounts -> run job -> poll status."""

from __future__ import annotations

import os
import time
from urllib.request import Request, urlopen
import json


def _request(method: str, url: str, payload: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = Request(url=url, method=method, headers=headers, data=data)
    with urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, (json.loads(body) if body else {})


def main() -> None:
    api = os.environ.get("SMOKE_API_BASE", "http://backend:8000/api/v1").rstrip("/")
    web = os.environ.get("SMOKE_WEB_URL", "http://frontend:3000")
    email = os.environ.get("SEED_ADMIN_EMAIL", "admin@example.com")
    password = os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMeNow123!")

    status, _ = _request("GET", f"{api}/health")
    if status != 200:
        raise SystemExit(f"health failed: {status}")
    print("health ok")

    status, login = _request("POST", f"{api}/auth/login", {"email": email, "password": password})
    if status != 200:
        raise SystemExit(f"login failed: {status}")
    token = login["access_token"]
    print("login ok")

    status, accounts = _request("GET", f"{api}/ad-accounts", token=token)
    if status != 200:
        raise SystemExit(f"ad-accounts failed: {status}")
    if not accounts:
        raise SystemExit("no accounts found; run seed_demo_data.py first")
    account_id = accounts[0]["id"]
    print(f"account ok: {account_id}")

    status, job = _request("POST", f"{api}/audits/l1/run-job", {"account_id": account_id}, token=token)
    if status != 202:
        raise SystemExit(f"run-job failed: {status}")
    task_id = job["task_id"]
    print(f"job queued: {task_id}")

    for _ in range(30):
        time.sleep(1)
        status, info = _request("GET", f"{api}/audits/jobs/{task_id}", token=token)
        if status != 200:
            continue
        if info.get("ready"):
            print(f"job done: state={info.get('state')} successful={info.get('successful')}")
            break
    else:
        raise SystemExit("job polling timeout")

    req = Request(url=f"{web}/login", method="GET")
    with urlopen(req, timeout=20) as resp:
        if resp.status != 200:
            raise SystemExit(f"frontend check failed: {resp.status}")
    print("frontend /login ok")

    print("smoke flow passed")


if __name__ == "__main__":
    main()
