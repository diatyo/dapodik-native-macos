#!/usr/bin/env python3
"""Assemble the Intel runtime from pinned upstream downloads."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from urllib.parse import quote
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "native-runtime"
PREFIX = RUNTIME / "root/opt/local"


def acquire(entry, cache):
    archive = cache / entry["name"]
    if not archive.exists():
        url = quote(entry["url"], safe=":/")
        partial = archive.with_suffix(archive.suffix + ".part")
        try:
            with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if hashlib.sha256(partial.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError(f"Checksum mismatch: {entry['name']}")
            partial.rename(archive)
        finally:
            partial.unlink(missing_ok=True)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != entry["sha256"]:
        raise ValueError(f"Checksum mismatch: {archive}")
    return archive


def build(cache):
    if sys.platform != "darwin" or platform.machine() != "x86_64":
        raise SystemExit("This runtime requires Intel macOS.")
    cache.mkdir(parents=True, exist_ok=True)
    entries = json.loads((ROOT / "tools/runtime-lock.json").read_text())
    with ThreadPoolExecutor(max_workers=6) as pool:
        archives = list(pool.map(lambda entry: acquire(entry, cache), entries))
    for entry, archive in zip(entries, archives):
        group = entry["group"]
        target = RUNTIME / {"macports": "root", "ioncube": "ioncube", "php-source": "src"}[group]
        target.mkdir(parents=True, exist_ok=True)
        command = ["/usr/bin/tar", "-xf", str(archive), "-C", str(target)]
        if group == "macports":
            command.extend(["--include", "opt/local/*", "--include", "./opt/local/*"])
        subprocess.run(command, check=True)
    php = PREFIX / "bin/php72"
    extensions = PREFIX / "lib/php72/extensions/no-debug-non-zts-20170718"
    for binary, original, system in [
        (php, "/opt/local/lib/libxml2.2.dylib", "/usr/lib/libxml2.2.dylib"),
        (extensions / "curl.so", "/opt/local/lib/libcurl.4.dylib", "/usr/lib/libcurl.4.dylib"),
    ]:
        subprocess.run(["/usr/bin/install_name_tool", "-change", original, system, str(binary)], check=True)
    for script in ["build_pgsql.py", "build_zip.py"]:
        subprocess.run([sys.executable, str(ROOT / "tools" / script)], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=RUNTIME / "downloads")
    build(parser.parse_args().cache.resolve())
