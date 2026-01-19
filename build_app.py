#!/usr/bin/env python3
"""Build script for creating the macOS application bundle."""

import os
import subprocess
import sys
from pathlib import Path


def build_mac_app():
    """Build the macOS .app bundle using PyInstaller."""

    # Get the project root
    project_root = Path(__file__).parent

    # Ensure we're in the right directory
    os.chdir(project_root)

    print("📦 Building Virtual Manuscript Reviewer macOS App...")
    print("=" * 50)

    # Install dependencies if needed
    print("\n1. Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-e", ".", "-q"])
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller", "-q"])

    print("\n2. Creating application bundle...")

    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "Virtual Manuscript Reviewer",
        "--windowed",  # No console window
        "--onedir",  # Create a directory bundle (faster startup than onefile)
        "--noconfirm",  # Overwrite without asking
        "--clean",  # Clean cache

        # Icon (we'll create a simple one)
        # "--icon", "icon.icns",

        # Exclude conflicting packages
        "--exclude-module", "PyQt5",
        "--exclude-module", "PySide2",
        "--exclude-module", "PySide6",
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        "--exclude-module", "IPython",
        "--exclude-module", "notebook",
        "--exclude-module", "sphinx",
        "--exclude-module", "pytest",

        # Hidden imports that PyInstaller might miss
        "--hidden-import", "tiktoken_ext.openai_public",
        "--hidden-import", "tiktoken_ext",
        "--hidden-import", "PyQt6.sip",
        "--hidden-import", "reportlab.graphics.barcode.common",
        "--hidden-import", "reportlab.graphics.barcode.code39",
        "--hidden-import", "reportlab.graphics.barcode.code93",
        "--hidden-import", "reportlab.graphics.barcode.code128",
        "--hidden-import", "reportlab.graphics.barcode.usps",
        "--hidden-import", "reportlab.graphics.barcode.usps4s",
        "--hidden-import", "reportlab.graphics.barcode.ecc200datamatrix",

        # Collect all data files
        "--collect-data", "tiktoken",
        "--collect-data", "certifi",

        # The main entry point
        "src/virtual_manuscript_reviewer/gui.py",
    ]

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print("\n❌ Build failed!")
        return False

    # Move the app to a more accessible location
    app_path = project_root / "dist" / "Virtual Manuscript Reviewer.app"

    if app_path.exists():
        print("\n" + "=" * 50)
        print("✅ Build successful!")
        print(f"\n📍 App location: {app_path}")
        print("\nTo install:")
        print("  1. Open 'dist' folder")
        print("  2. Drag 'Virtual Manuscript Reviewer.app' to Applications")
        print("\n⚠️  Before running, set your OpenAI API key:")
        print("  export OPENAI_API_KEY='your-key-here'")
        print("\nOr add it to ~/.zshrc for permanent access.")
        return True
    else:
        print("\n❌ App bundle not found!")
        return False


def create_dmg():
    """Create a DMG installer (optional, requires create-dmg)."""
    print("\n3. Creating DMG installer...")

    try:
        subprocess.run([
            "create-dmg",
            "--volname", "Virtual Manuscript Reviewer",
            "--window-pos", "200", "120",
            "--window-size", "600", "400",
            "--icon-size", "100",
            "--app-drop-link", "450", "185",
            "dist/Virtual_Manuscript_Reviewer.dmg",
            "dist/Virtual Manuscript Reviewer.app"
        ], check=True)
        print("✅ DMG created: dist/Virtual_Manuscript_Reviewer.dmg")
    except FileNotFoundError:
        print("ℹ️  Skipping DMG creation (install create-dmg for this feature)")
    except subprocess.CalledProcessError:
        print("⚠️  DMG creation failed")


if __name__ == "__main__":
    if build_mac_app():
        # Optionally create DMG
        if "--dmg" in sys.argv:
            create_dmg()
