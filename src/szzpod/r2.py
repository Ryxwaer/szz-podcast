"""Step 4: upload the rendered mp3 to Cloudflare R2 via wrangler.

Requires `wrangler login` and a Cloudflare account id (from CLOUDFLARE_ACCOUNT_ID
or the config `r2.account_id`). The bucket is public, so the object becomes
reachable at ``{base_url}/{key}``.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def upload(audio_path: Path, r2_key: str, *, bucket: str, account_id: str) -> None:
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio not found: {audio_path}")

    env = os.environ.copy()
    env.setdefault("CLOUDFLARE_ACCOUNT_ID", account_id)

    cmd = [
        "npx", "--yes", "wrangler@latest", "r2", "object", "put",
        f"{bucket}/{r2_key}",
        "--file", str(audio_path),
        "--content-type", "audio/mpeg",
        "--remote",
    ]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"wrangler upload failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}"
        )
