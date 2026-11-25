"""Install project-local build tools from their official distribution endpoints."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
import urllib.error
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tooling"
TOOLS.mkdir(exist_ok=True)


def download(url: str, target: Path, expected_hash: str | None = None) -> Path:
    if not target.exists():
        print(f"Downloading {target.name}", flush=True)
        request = urllib.request.Request(url, headers={"User-Agent": "TushumAI-build/1.0"})
        with (
            urllib.request.urlopen(request, timeout=90) as response,
            target.with_suffix(".part").open("wb") as output,
        ):
            downloaded = 0
            last_report = 0
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                downloaded += len(chunk)
                if downloaded - last_report >= 100 * 1024 * 1024:
                    print(f"{downloaded // (1024 * 1024)} MB", flush=True)
                    last_report = downloaded
        target.with_suffix(".part").replace(target)
    if expected_hash:
        with target.open("rb") as source:
            actual = hashlib.file_digest(source, "sha256").hexdigest()
        if actual != expected_hash:
            raise RuntimeError(f"Checksum mismatch for {target.name}")
    return target


def flutter() -> None:
    if (TOOLS / "flutter/bin/flutter.bat").exists():
        return
    try:
        with urllib.request.urlopen(
            "https://storage.googleapis.com/flutter_infra_release/flutter/releases/releases_windows.json",
            timeout=40,
        ) as source:
            metadata = json.load(source)
    except urllib.error.HTTPError:
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                "3.50.0",
                "https://github.com/flutter/flutter.git",
                str(TOOLS / "flutter"),
            ],
            check=True,
        )
        return
    release = next(
        item
        for item in metadata["releases"]
        if item["hash"] == metadata["current_release"]["stable"]
    )
    archive = download(
        metadata["base_url"] + "/" + release["archive"], TOOLS / "flutter.zip", release["sha256"]
    )
    print(f"Extracting Flutter {release['version']}", flush=True)
    with zipfile.ZipFile(archive) as package:
        package.extractall(TOOLS)
    (TOOLS / "flutter-release.json").write_text(json.dumps(release, indent=2), encoding="utf-8")


def android() -> None:
    if not (TOOLS / "java").exists():
        endpoint = "https://api.adoptium.net/v3/assets/latest/17/hotspot?architecture=x64&image_type=jdk&os=windows&vendor=eclipse"
        try:
            with urllib.request.urlopen(endpoint, timeout=40) as source:
                asset = json.load(source)[0]["binary"]["package"]
        except urllib.error.HTTPError:
            link = "https://download.java.net/java/GA/jdk21.0.2/f2283984656d49d69e91c558476027ac/13/GPL/openjdk-21.0.2_windows-x64_bin.zip"
            with urllib.request.urlopen(link + ".sha256", timeout=40) as source:
                checksum = source.read().decode().split()[0]
            asset = {"link": link, "checksum": checksum}
        archive = download(asset["link"], TOOLS / "jdk.zip", asset["checksum"])
        with zipfile.ZipFile(archive) as package:
            folder = package.namelist()[0].split("/")[0]
            package.extractall(TOOLS)
        (TOOLS / folder).rename(TOOLS / "java")
    sdk = TOOLS / "android-sdk"
    manager = sdk / "cmdline-tools/latest/bin/sdkmanager.bat"
    if not manager.exists():
        archive = download(
            "https://dl.google.com/android/repository/commandlinetools-win-13114758_latest.zip",
            TOOLS / "android-commandline.zip",
        )
        staging = TOOLS / "android-commandline"
        with zipfile.ZipFile(archive) as package:
            package.extractall(staging)
        manager.parent.parent.parent.mkdir(parents=True, exist_ok=True)
        (staging / "cmdline-tools").rename(manager.parent.parent)
    environment = os.environ.copy()
    environment["JAVA_HOME"] = str(TOOLS / "java")
    environment["ANDROID_HOME"] = str(sdk)
    environment["ANDROID_USER_HOME"] = str(TOOLS / "android-home")
    environment["PATH"] = str(TOOLS / "java/bin") + os.pathsep + environment["PATH"]
    subprocess.run(
        [str(manager), f"--sdk_root={sdk}", "--licenses"],
        input="y\n" * 100,
        text=True,
        env=environment,
        check=True,
    )
    subprocess.run(
        [
            str(manager),
            f"--sdk_root={sdk}",
            "platform-tools",
            "platforms;android-36",
            "build-tools;35.0.0",
            "build-tools;36.0.0",
        ],
        env=environment,
        check=True,
    )


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "flutter"
    if mode == "flutter":
        flutter()
    elif mode == "android":
        android()
    else:
        raise SystemExit("Expected flutter or android")
