#!/usr/bin/env python3
"""Install Dapodik 2027.b from the user's three known Windows installers."""
import argparse
from contextlib import contextmanager
import getpass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "native-runtime"
DEFAULT_DEST = Path.home() / "Library/Application Support/Dapodik Native"
BUNDLE = Path.home() / "Applications/Dapodik Native.app"
INPUTS = {
    "Dapodik_2027.exe": "4a434ab4a267b9a1d5660b85351774c90dda54050a5964b999e97b07e8162aee",
    "Patch_Dapodik_2027.a.exe": "a3c39d3bac9f294a5edc236c7a531436ab900c29f2fd193772fa31707e60d90e",
    "Patch_Dapodik_2027.b.exe": "72a0ec3886539504bd379160a65cc45b85d8aeb6c45b37f4b6dd03577e8131a3",
}


def run(args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def extract(installers, staging):
    prefix = RUNTIME / "root/opt/local"
    env = dict(os.environ, DYLD_LIBRARY_PATH=f"{prefix}/lib:{prefix}/libexec/boost/1.81/lib")
    for index, (name, digest) in enumerate(INPUTS.items()):
        path = installers / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Unknown installer build: {name}")
        run([prefix / "bin/innoextract", "--silent", "--extract", "--output-dir", staging / str(index), path], env=env)


def stage(destination, staging):
    base = staging / "0/app"
    app = destination / "app"
    app.mkdir()
    for name in ["config", "dataweb"]:
        shutil.copytree(base / name, app / name)
    for index in [1, 2]:
        shutil.copytree(staging / f"{index}/app/dataweb", app / "dataweb", dirs_exist_ok=True)
    modules = app / "webserver/modules"
    modules.mkdir(parents=True)
    shutil.copy2(base / "webserver/modules/mod_sied.so", modules)
    app_config = app / "dataweb/apps/app/config/conf"
    app_tmp = app / "dataweb/apps/tmp"
    app_tmp.mkdir(exist_ok=True)
    shutil.copy2(app / "config/pendataan-conf.php", app_tmp)
    for target in [app / "config", app_tmp]:
        shutil.copy2(app_config / "classmap-pendataan-conf.php", target)
    for directory in [app / "config", app_config, app_tmp]:
        original = directory / "pendataan-conf.php"
        original.rename(directory / "pendataan-conf.upstream.php")
        shutil.copy2(ROOT / "tools/pendataan-conf.php", original)
    run([sys.executable, ROOT / "tools/adapt_native_prefill.py", app / "dataweb/synch_dikdas"])
    for name in ["control.py", "router.php"]:
        shutil.copy2(ROOT / "native-macos" / name, destination / name)
    runtime = destination / "runtime"
    runtime.mkdir()
    for name in ["root", "extensions", "ioncube"]:
        shutil.copytree(RUNTIME / name, runtime / name, symlinks=True)
    (destination / "manifest.json").write_text(json.dumps({"application_version": "2027.b", "installers": INPUTS}, indent=2) + "\n")


@contextmanager
def postgres_for_bootstrap(control, destination, socket_dir, env):
    log = destination / "logs/bootstrap-postgres.log"
    with log.open("wb") as output:
        process = subprocess.Popen(
            [str(control.PG / "postgres"), "-D", str(destination / "database"), "-h", "",
             "-p", str(control.PORT), "-k", str(socket_dir)],
            env=env, stdout=output, stderr=output,
        )
        try:
            import time
            for _ in range(100):
                if process.poll() is not None:
                    break
                ready = subprocess.run(
                    [str(control.PG / "psql"), "-X", "-h", str(socket_dir), "-p",
                     str(control.PORT), "-U", "postgres", "-d", "postgres", "-c", "SELECT 1"],
                    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                if ready.returncode == 0:
                    yield
                    return
                time.sleep(.1)
            raise RuntimeError(f"Bootstrap PostgreSQL failed. See {log}")
        finally:
            if process.poll() is None:
                run([control.PG / "pg_ctl", "-D", destination / "database", "-m", "fast", "-w", "stop"], env=env)
                process.wait(timeout=15)


def bootstrap(destination, staging):
    spec = importlib.util.spec_from_file_location("dapodik_control", destination / "control.py")
    control = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(control)
    control.configure()
    env = control.environment()
    db_dir = destination / "database"
    run([control.PG / "initdb", "-D", db_dir, "-U", "postgres", "--encoding=UTF8", "--locale=C", "-A", "peer"], env=env, stdout=subprocess.DEVNULL)
    user = getpass.getuser()
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+", user):
        raise ValueError("The macOS account name must be usable in pg_ident.conf.")
    (db_dir / "pg_ident.conf").write_text(f"dapodik_native {user} postgres\ndapodik_native {user} dapodik_user\n")
    (db_dir / "pg_hba.conf").write_text(
        "local all postgres peer map=dapodik_native\n"
        "local all dapodik_user peer map=dapodik_native\n"
        "local all all reject\nhost all all 127.0.0.1/32 reject\nhost all all ::1/128 reject\n"
    )
    dumps = staging / "0/app/temp"
    bootstrap_sql = staging / "dapodik_app-pg92.sql"
    sql = (dumps / "dapodik_app.sql").read_text()
    bootstrap_sql.write_text(re.sub(
        r"^SET (?:lock_timeout|idle_in_transaction_session_timeout|row_security) = [^;]+;\n",
        "", sql, flags=re.M,
    ))
    with TemporaryDirectory(prefix="dapodik-pg-", dir="/tmp") as socket_dir:
        connection = ["-h", socket_dir, "-p", str(control.PORT), "-U", "postgres"]
        with postgres_for_bootstrap(control, destination, socket_dir, env):
            run([control.PG / "psql", "-X", *connection, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", "CREATE ROLE dapodik_user LOGIN"], env=env)
            for name, source in [("pendataan", dumps / "pendataan.sql"), ("dapodik_app", bootstrap_sql)]:
                run([control.PG / "createdb", *connection, name], env=env)
                with (destination / f"logs/restore-{name}.log").open("wb") as log:
                    run([control.PG / "psql", "-X", *connection, "-d", name, "-v", "ON_ERROR_STOP=1", "--single-transaction", "-f", source], env=env, stdout=log, stderr=log)


def create_launcher(destination):
    contents = BUNDLE / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    info = {
        "CFBundleName": "Dapodik Native", "CFBundleIdentifier": "org.dapodik-native.local",
        "CFBundleExecutable": "DapodikNative", "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "2027.2", "CFBundleVersion": "2027.2", "LSUIElement": True,
    }
    (contents / "Info.plist").write_bytes(plistlib.dumps(info))
    launcher = contents / "MacOS/DapodikNative"
    script = shlex.quote(str(destination / "control.py"))
    log = shlex.quote(str(destination / "launch.log"))
    launcher.write_text(f"#!/bin/sh\nexec /usr/bin/python3 {script} start --open >> {log} 2>&1\n")
    launcher.chmod(0o755)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("installers", type=Path, help="directory holding the three official EXE installers")
    parser.add_argument("--destination", type=Path, default=DEFAULT_DEST)
    parser.add_argument("--no-start", action="store_true")
    args = parser.parse_args()
    destination = args.destination.resolve()
    default_install = destination == DEFAULT_DEST.resolve()
    if os.geteuid() == 0:
        raise SystemExit("Run as your regular macOS user.")
    if destination.exists() or (default_install and BUNDLE.exists()):
        raise SystemExit("An installation already exists. Choose an unused destination.")
    with TemporaryDirectory(prefix="dapodik-install-") as temp:
        staging = Path(temp)
        extract(args.installers.resolve(), staging)
        destination.mkdir(parents=True, mode=0o700)
        stage(destination, staging)
        bootstrap(destination, staging)
    if default_install:
        create_launcher(destination)
    if not args.no_start:
        run([sys.executable, destination / "control.py", "start"])
    print(f"Installed at {destination}")
