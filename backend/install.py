"""
install.py — One-shot dependency installer for RoadSense AI
Run:  python install.py
"""

import subprocess
import sys
import os

PACKAGES = [
    "ultralytics>=8.0.200",
    "opencv-python>=4.8.0",
    "numpy>=1.24.0",
    "deep-sort-realtime>=1.3.2",
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "python-multipart>=0.0.6",
    "websockets>=12.0",
    "aiofiles>=23.2.1",
    "groq>=0.4.1",
    "pydantic>=2.4.0",
    "python-dotenv>=1.0.0",
    "Pillow>=10.0.0",
    "scipy>=1.11.0",
]


def pip(*args):
    subprocess.check_call([sys.executable, "-m", "pip", *args])


def main():
    print("=" * 60)
    print("  RoadSense AI — Dependency Installer")
    print("=" * 60)

    pip("install", "--upgrade", "pip")

    for pkg in PACKAGES:
        print(f"\n[+] Installing: {pkg}")
        try:
            pip("install", pkg)
        except subprocess.CalledProcessError as e:
            print(f"[!] Failed to install {pkg}: {e}")

    print("\n" + "=" * 60)
    print("  Installation complete!")
    print("  Run the server:  python -m uvicorn main:app --port 8000")
    print("=" * 60)


if __name__ == "__main__":
    main()
