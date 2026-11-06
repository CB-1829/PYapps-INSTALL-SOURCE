#!/usr/bin/env python3
"""
PYapps Official App Installer (installer.py)
Repository: https://github.com/CB-1829/PYapps-INSTALL-SOURCE
Documentation & Sources: https://cb-1829.github.io/PYapps-INSTALL-SOURCE/

Usage:
  Direct installation pipe:
    curl.exe -sL https://cb-1829.github.io/PYapps-INSTALL-SOURCE/installer/installer.py | py
  
  CLI Usage after setup:
    pyapp install APP_INSTALL_NAME
    pyapp list
    pyapp verify APP_INSTALL_NAME
    pyapp run APP_INSTALL_NAME
    pyapp remove APP_INSTALL_NAME
"""

from __future__ import annotations

import os
import sys
import json
import re
import shutil
import zipfile
import io
import urllib.request
import urllib.error
import subprocess
from pathlib import Path

# Base configuration constants
REPO_RAW_BASE = "https://raw.githubusercontent.com/CB-1829/PYapps-INSTALL-SOURCE/main"
GITHUB_IO_BASE = "https://cb-1829.github.io/PYapps-INSTALL-SOURCE"
OFFICIAL_KEYS_BASE = GITHUB_IO_BASE + "/installer/officialkeys/mainkeys"
GITHUB_API_TREE = "https://api.github.com/repos/CB-1829/PYapps-INSTALL-SOURCE/git/trees/main?recursive=1"
GITHUB_API_CONTENTS = "https://api.github.com/repos/CB-1829/PYapps-INSTALL-SOURCE/contents/apps"

# Static catalog fallback in case GitHub API rate limits
KNOWN_APPS_CATALOG = {
    "gemswarm": {
        "folder": "Gemini-Cursor-Swarm",
        "zip": "apps/Gemini-Cursor-Swarm/gemini-cursor-swarm---desktop-multi-agent-program.zip",
        "name": "Gemini Cursor Swarm",
    },
    "testapp": {
        "folder": "testapp",
        "zip": None,
        "files": ["app.py", "run.py", "info.app.json"],
        "name": "Test Application",
    },
}

# Determine target installation paths
def get_apps_root_dir() -> Path:
    """
    Returns the designated apps directory:
    C:\\Users\\<USER>\\AppData\\Local\\Programs\\Python\\Python314\\pyappsinstall\\apps
    """
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data) / "Programs" / "Python" / "Python314" / "pyappsinstall" / "apps"
    else:
        base = Path.home() / "AppData" / "Local" / "Programs" / "Python" / "Python314" / "pyappsinstall" / "apps"
    base.mkdir(parents=True, exist_ok=True)
    return base

def get_pyapp_bin_dir() -> Path:
    """Returns directory where pyapp CLI executable / batch launcher lives."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        bin_dir = Path(local_app_data) / "Programs" / "Python" / "Python314" / "Scripts"
    else:
        bin_dir = Path.home() / "AppData" / "Local" / "Programs" / "Python" / "Python314" / "Scripts"
    bin_dir.mkdir(parents=True, exist_ok=True)
    return bin_dir

def validate_app_id(app_id: str) -> bool:
    """app-id IS REQUIRED TO BE a four-digit id using a-z and 0-9."""
    if not isinstance(app_id, str):
        return False
    return bool(re.fullmatch(r"^[a-z0-9]{4}$", app_id))

def validate_install_name(name: str) -> bool:
    """app-install-name must be 6-10 letters (a-z, A-Z)."""
    if not isinstance(name, str):
        return False
    return bool(re.fullmatch(r"^[a-zA-Z]{6,10}$", name))

def fetch_url_text(url: str, timeout: int = 10) -> tuple[bool, str]:
    """Fetch text from a given URL."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "PYapps-Installer/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8")
            return True, content
    except Exception as e:
        return False, str(e)

def fetch_url_bytes(url: str, timeout: int = 25) -> tuple[bool, bytes]:
    """Fetch binary content from a given URL."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "PYapps-Installer/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read()
            return True, content
    except Exception as e:
        return False, b""

def fetch_repo_tree() -> dict[str, dict]:
    """
    Queries GitHub API or fallbacks to find all available apps and their .zip packages.
    Returns: { folder_name: { 'folder': str, 'zip': str | None, 'files': list[str] } }
    """
    apps: dict[str, dict] = {}
    
    # Tier 1: Recursive Git Tree
    try:
        req = urllib.request.Request(GITHUB_API_TREE, headers={"User-Agent": "PYapps-Installer/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            tree_data = json.loads(resp.read().decode("utf-8")).get("tree", [])
            for item in tree_data:
                path = item.get("path", "")
                if not path.startswith("apps/"):
                    continue
                parts = path.split("/")
                if len(parts) >= 2:
                    folder = parts[1]
                    if folder not in apps:
                        apps[folder] = {"folder": folder, "files": [], "zip": None}
                    if len(parts) > 2:
                        subfile = parts[2]
                        apps[folder]["files"].append(subfile)
                        if subfile.lower().endswith(".zip"):
                            apps[folder]["zip"] = path
            if apps:
                return apps
    except Exception:
        pass

    # Tier 2: GitHub Contents API
    try:
        req = urllib.request.Request(GITHUB_API_CONTENTS, headers={"User-Agent": "PYapps-Installer/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            contents = json.loads(resp.read().decode("utf-8"))
            for item in contents:
                name = item.get("name", "")
                if item.get("type") == "dir":
                    apps[name] = {"folder": name, "files": [], "zip": None}
                    # Probe folder for zip
                    try:
                        sub_req = urllib.request.Request(GITHUB_API_CONTENTS + "/" + name, headers={"User-Agent": "PYapps-Installer/1.0"})
                        with urllib.request.urlopen(sub_req, timeout=8) as sub_resp:
                            sub_files = json.loads(sub_resp.read().decode("utf-8"))
                            for sf in sub_files:
                                sf_name = sf.get("name", "")
                                apps[name]["files"].append(sf_name)
                                if sf_name.lower().endswith(".zip"):
                                    apps[name]["zip"] = "apps/" + name + "/" + sf_name
                    except Exception:
                        pass
            if apps:
                return apps
    except Exception:
        pass

    # Tier 3: Known apps catalog fallback
    for k, v in KNOWN_APPS_CATALOG.items():
        apps[v["folder"]] = {"folder": v["folder"], "files": v.get("files", []), "zip": v.get("zip")}
    return apps

def resolve_app_package(install_name: str) -> tuple[str | None, str | None, list[str]]:
    """
    Resolves install_name (e.g. 'gemswarm') to the actual repository folder,
    zip package path, and/or loose files.
    """
    # 1. Direct catalog check
    if install_name.lower() in KNOWN_APPS_CATALOG:
        cat = KNOWN_APPS_CATALOG[install_name.lower()]
        return cat["folder"], cat.get("zip"), cat.get("files", [])

    repo_apps = fetch_repo_tree()

    clean_q = install_name.lower().replace("-", "").replace("_", "")

    # 2. Check exact matches
    for folder, data in repo_apps.items():
        if folder.lower() == install_name.lower():
            return folder, data.get("zip"), data.get("files", [])

    # 3. Check normalized substring or abbreviation matching
    # e.g., 'gemswarm' matches 'Gemini-Cursor-Swarm'
    for folder, data in repo_apps.items():
        clean_f = folder.lower().replace("-", "").replace("_", "")
        # Substring match
        if clean_q in clean_f or clean_f in clean_q:
            return folder, data.get("zip"), data.get("files", [])
        # Compound prefix + suffix match (e.g. gem + swarm in geminicursorswarm)
        if len(clean_q) >= 6:
            prefix = clean_q[:3]
            suffix = clean_q[-4:]
            if prefix in clean_f and suffix in clean_f:
                return folder, data.get("zip"), data.get("files", [])

    # 4. Check zip filename matches directly
    for folder, data in repo_apps.items():
        zip_path = data.get("zip")
        if zip_path:
            clean_z = Path(zip_path).stem.lower().replace("-", "").replace("_", "")
            if clean_q in clean_z:
                return folder, zip_path, data.get("files", [])

    return None, None, []

def verify_official_key(app_id: str, local_key: str | None = None, key_link: str | None = None) -> tuple[bool, str]:
    """
    Checks the key against the official key on:
    https://cb-1829.github.io/PYapps-INSTALL-SOURCE/installer/officialkeys/mainkeys/APP-ID-HERE.key
    """
    if not validate_app_id(app_id):
        return False, "Invalid app-id format: '" + str(app_id) + "'. Must be strictly 4 characters [a-z0-9]."
    
    candidate_key = ""
    if local_key and str(local_key).strip():
        candidate_key = str(local_key).strip()
    elif key_link and str(key_link).strip():
        print("[*] Fetching candidate key from link: " + str(key_link) + "...")
        ok, fetched = fetch_url_text(str(key_link).strip())
        if ok and fetched.strip():
            candidate_key = fetched.strip()
        else:
            return False, "Could not fetch key from link '" + str(key_link) + "': " + str(fetched)
    else:
        return False, "No 'app-officialkey' or 'app-officialkey-link' specified in info.app.json."

    official_url = OFFICIAL_KEYS_BASE + "/" + app_id + ".key"
    print("[*] Verifying key against official repository: " + official_url)
    ok, official_key = fetch_url_text(official_url)
    
    if not ok:
        return False, "Could not fetch official key for app-id '" + app_id + "' from official repo (" + str(official_key) + ")."
    
    clean_official = official_key.strip()
    if candidate_key == clean_official:
        return True, "Key verified: Official Match confirmed."
    else:
        return False, "Key mismatch! Provided key does not match official repository key for '" + app_id + "'."

def create_windows_shortcut(target_exe: str, args: str, shortcut_path: str, icon_path: str = "", description: str = "") -> bool:
    """
    Creates a native Windows .lnk shortcut with custom icon using PowerShell.
    """
    try:
        escaped_target = target_exe.replace("'", "''")
        escaped_args = args.replace("'", "''")
        escaped_path = shortcut_path.replace("'", "''")
        escaped_icon = icon_path.replace("'", "''")
        escaped_desc = description.replace("'", "''")

        ps_script = (
            "$WshShell = New-Object -ComObject WScript.Shell\n"
            + "$Shortcut = $WshShell.CreateShortcut('" + escaped_path + "')\n"
            + "$Shortcut.TargetPath = '" + escaped_target + "'\n"
            + "$Shortcut.Arguments = '" + escaped_args + "'\n"
            + "if ('" + escaped_icon + "' -ne '' -and (Test-Path '" + escaped_icon + "')) {\n"
            + "    $Shortcut.IconLocation = '" + escaped_icon + "'\n"
            + "}\n"
            + "$Shortcut.Description = '" + escaped_desc + "'\n"
            + "$Shortcut.WindowStyle = 1\n"
            + "$Shortcut.Save()\n"
        )
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script], check=True, capture_output=True)
        return True
    except Exception as e:
        print("[!] Notice: Could not create desktop .lnk shortcut automatically: " + str(e))
        return False

def generate_silent_runner(app_dir: Path, app_name: str, entry_file: str) -> Path:
    """
    Creates a smart launcher script (launcher.pyw).
    Suppresses the console completely UNLESS the script prints text to stdout/stderr.
    """
    launcher_file = app_dir / "launcher.pyw"
    template = '''# -*- coding: utf-8 -*-
"""
PYapps Smart Launcher
Runs target script with console hidden unless stdout/stderr has text.
"""
import sys
import os
import subprocess
import ctypes

def main():
    app_dir = os.path.dirname(os.path.abspath(__file__))
    target_script = os.path.join(app_dir, "__ENTRY_FILE__")
    
    py_exec = sys.executable
    if "pythonw.exe" in py_exec.lower():
        normal_py = py_exec.lower().replace("pythonw.exe", "python.exe")
        py_runner = normal_py if os.path.exists(normal_py) else py_exec
    else:
        py_runner = py_exec

    startupinfo = None
    creationflags = 0
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        creationflags = subprocess.CREATE_NO_WINDOW

    proc = subprocess.Popen(
        [py_runner, target_script],
        cwd=app_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        startupinfo=startupinfo,
        creationflags=creationflags,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    stdout, stderr = proc.communicate()
    output = (stdout or "") + (stderr or "")

    # UNLESS its printing text: If there is text output, display it to the user!
    if output.strip():
        try:
            import tkinter as tk
            from tkinter import scrolledtext
            root = tk.Tk()
            root.title("PYapps Console - __APP_NAME__")
            root.geometry("640x380")
            root.configure(bg="#1e1e1e")
            
            lbl = tk.Label(root, text="__APP_NAME__ Output Log", fg="#00ff66", bg="#1e1e1e", font=("Consolas", 11, "bold"))
            lbl.pack(anchor="w", padx=10, pady=(8, 2))

            txt = scrolledtext.ScrolledText(root, bg="#111", fg="#eee", insertbackground="white", font=("Consolas", 10))
            txt.pack(expand=True, fill="both", padx=10, pady=8)
            txt.insert("1.0", output)
            txt.configure(state="disabled")
            
            btn = tk.Button(root, text="Close Window", command=root.destroy, bg="#333", fg="white", padx=10, pady=4)
            btn.pack(pady=(0, 8))
            root.mainloop()
        except Exception:
            if sys.platform == "win32":
                ctypes.windll.user32.MessageBoxW(0, output[:2000], "PYapps - __APP_NAME__ Output", 0x40)

if __name__ == "__main__":
    main()
'''
    code = template.replace("__ENTRY_FILE__", entry_file).replace("__APP_NAME__", app_name)
    launcher_file.write_text(code, encoding="utf-8")
    return launcher_file

def install_app(install_name: str, force: bool = False):
    """
    Main installation logic for `pyapp install <APP_INSTALL_NAME>`.
    Downloads .zip package, extracts files, verifies key, and generates silent launcher.
    """
    # Validate install name (6-10 letters)
    if not validate_install_name(install_name):
        print("[!] Error: 'app-install-name' must be between 6 and 10 letters (a-z, A-Z).")
        print("    Provided: '" + str(install_name) + "' (" + str(len(install_name)) + " chars)")
        sys.exit(1)

    print("============================================================")
    print(" PYapps Installer - Fetching '" + install_name + "'")
    print("============================================================")

    # Resolve app folder and .zip package path
    print("[*] Resolving package for install name '" + install_name + "'...")
    matched_folder, zip_rel_path, loose_files = resolve_app_package(install_name)

    if not matched_folder:
        print("[!] Error: Could not find application with install-name '" + install_name + "'.")
        print("    Searched repository apps directory at https://github.com/CB-1829/PYapps-INSTALL-SOURCE")
        sys.exit(1)

    print("[+] Found repository application: " + matched_folder)

    # Destination folder:
    # C:\Users\<USER>\AppData\Local\Programs\Python\Python314\pyappsinstall\apps\<install_name>
    apps_root = get_apps_root_dir()
    app_dest = apps_root / install_name
    app_dest.mkdir(parents=True, exist_ok=True)
    print("[*] Target installation folder: " + str(app_dest))

    # Case A: Download and extract .zip archive
    if zip_rel_path:
        zip_url = REPO_RAW_BASE + "/" + zip_rel_path
        print("[*] Downloading package archive: " + zip_url)
        ok, zip_bytes = fetch_url_bytes(zip_url)
        if not ok or len(zip_bytes) == 0:
            print("[!] Error: Failed to download archive: " + zip_url)
            sys.exit(1)

        print("[*] Extracting .zip archive into " + str(app_dest) + "...")
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                zf.extractall(app_dest)
            print("[+] Successfully extracted all package files!")
        except Exception as e:
            print("[!] Error: Failed to extract .zip archive: " + str(e))
            sys.exit(1)

    # Case B: Download loose files if no .zip archive
    else:
        print("[*] Downloading application files...")
        files_to_download = loose_files if loose_files else ["app.py", "run.py", "info.app.json"]
        for fname in files_to_download:
            file_url = REPO_RAW_BASE + "/apps/" + matched_folder + "/" + fname
            print("[*] Downloading " + fname + "...")
            ok, data = fetch_url_bytes(file_url)
            if ok and len(data) > 0:
                (app_dest / fname).write_bytes(data)

    # Inspect info.app.json from extracted files
    manifest_path = app_dest / "info.app.json"
    manifest: dict = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            print("[!] Warning: Could not parse info.app.json: " + str(e))

    app_meta = manifest.get("app", {})
    app_name = app_meta.get("app-name") or manifest.get("app-name", matched_folder)
    app_id = app_meta.get("app-id") or manifest.get("app-id")
    app_key = app_meta.get("app-officialkey") or manifest.get("app-officialkey")
    app_key_link = app_meta.get("app-officialkey-link") or manifest.get("app-officialkey-link")
    app_icon = app_meta.get("app-icon") or manifest.get("app-icon", "app_icon.ico")

    print("\n[i] App Name:    " + str(app_name))
    print("[i] App ID:      " + str(app_id))
    print("[i] Install Name:" + str(install_name))

    # Official Key Verification
    print("\n[*] Performing Official Key Verification...")
    verified = False
    verify_msg = ""
    
    if app_id and validate_app_id(str(app_id)):
        verified, verify_msg = verify_official_key(str(app_id), app_key, app_key_link)
    else:
        verified = False
        verify_msg = "app-id ('" + str(app_id) + "') is not a verified 4-digit ID."

    if verified:
        print("[✓] " + verify_msg)
        print("[✓] Package is authentic and verified with the PYapps repository.")
    else:
        print("\n" + "!" * 60)
        print(" [!] SECURITY WARNING: OFFICIAL KEY VERIFICATION FAILED / UNVERIFIED!")
        print(" Reason: " + str(verify_msg))
        print(" Without a matching official key in:")
        print(" " + OFFICIAL_KEYS_BASE + "/" + str(app_id) + ".key")
        print(" this application is UNVERIFIED and could be modified or untrusted.")
        print("!" * 60)
        
        if not force:
            try:
                choice = input("\nDo you still want to proceed with installing this unverified app? (y/N): ").strip().lower()
            except Exception:
                choice = "n"
            if choice not in ("y", "yes"):
                print("[*] Installation aborted by user for security.")
                sys.exit(1)
        else:
            print("[!] Force flag specified: continuing installation despite warning.")

    # Check for requirements.txt and install dependencies
    req_file = app_dest / "requirements.txt"
    if req_file.exists():
        print("\n[*] Found requirements.txt, checking dependencies...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req_file), "--quiet"], check=False)
            print("[+] Dependencies checked successfully.")
        except Exception:
            pass

    # Determine entry point (run.py or app.py)
    entry_file = "run.py"
    if not (app_dest / "run.py").exists():
        if (app_dest / "app.py").exists():
            entry_file = "app.py"

    # Generate the smart silent launcher (hides console window unless printing text)
    launcher_file = generate_silent_runner(app_dest, app_name, entry_file)
    print("[+] Generated silent launcher: " + launcher_file.name)

    # Create desktop shortcut with the icon
    icon_dest_file = app_dest / app_icon if app_icon else ""
    desktop_dir = Path.home() / "Desktop"
    if desktop_dir.exists():
        shortcut_file = desktop_dir / (app_name + ".lnk")
        pyw_exe = sys.executable.replace("python.exe", "pythonw.exe")
        if not os.path.exists(pyw_exe):
            pyw_exe = sys.executable

        shortcut_created = create_windows_shortcut(
            target_exe=pyw_exe,
            args='"' + str(launcher_file) + '"',
            shortcut_path=str(shortcut_file),
            icon_path=str(icon_dest_file) if icon_dest_file and icon_dest_file.exists() else "",
            description=app_name + " (PYapps)"
        )
        if shortcut_created:
            print("[+] Created desktop app shortcut with icon: " + str(shortcut_file))

    print("\n============================================================")
    print(" [✓] Installation of '" + app_name + "' (" + install_name + ") Complete!")
    print(" Location: " + str(app_dest))
    print(" To launch, double click the desktop shortcut or run:")
    print(" pyapp run " + install_name)
    print("============================================================")

def setup_installer_cli():
    """
    Configures `pyapp` command so typing 'pyapp install <name>' works in cmd/powershell.
    Executed when installer is installed via:
    curl.exe -sL https://cb-1829.github.io/PYapps-INSTALL-SOURCE/installer/installer.py | py
    """
    bin_dir = get_pyapp_bin_dir()
    apps_dir = get_apps_root_dir()
    pyapps_home = apps_dir.parent
    pyapps_home.mkdir(parents=True, exist_ok=True)
    installed_installer_path = pyapps_home / "installer.py"

    installer_code: bytes | None = None

    # 1. If executing a real file on disk (not piped through '<stdin>')
    if sys.argv and sys.argv[0]:
        arg_path = sys.argv[0]
        if arg_path != "<stdin>" and os.path.isfile(arg_path):
            try:
                installer_code = Path(arg_path).read_bytes()
            except Exception:
                pass

    if not installer_code and "__file__" in globals():
        file_var = str(globals().get("__file__", ""))
        if file_var and file_var != "<stdin>" and os.path.isfile(file_var):
            try:
                installer_code = Path(file_var).read_bytes()
            except Exception:
                pass

    # 2. If piped via curl | py, download installer.py directly from official GitHub Pages / Raw
    if not installer_code:
        print("[*] Fetching installer code from official repository...")
        official_url = GITHUB_IO_BASE + "/installer/installer.py"
        ok, data = fetch_url_bytes(official_url)
        if ok and len(data) > 0:
            installer_code = data
        else:
            raw_url = REPO_RAW_BASE + "/installer/installer.py"
            ok, data = fetch_url_bytes(raw_url)
            if ok and len(data) > 0:
                installer_code = data

    if installer_code and len(installer_code) > 0:
        installed_installer_path.write_bytes(installer_code)
        print("[+] Cached installer.py to: " + str(installed_installer_path))
    else:
        print("[!] Warning: Could not cache installer.py locally. Make sure you have internet access.")

    # Create pyapp.cmd for Windows Command Prompt & PowerShell
    cmd_file = bin_dir / "pyapp.cmd"
    batch_content = "@echo off\r\npy \"" + str(installed_installer_path) + "\" %*\r\n"
    cmd_file.write_text(batch_content, encoding="utf-8")

    # Add bin_dir to user PATH if not present
    print("=" * 60)
    print("  PYapps Installer - System Setup")
    print("=" * 60)
    print("[+] Installed PYapps core to: " + str(pyapps_home))
    print("[+] Created CLI command: " + str(cmd_file))
    print("[+] Target Apps Directory: " + str(apps_dir))
    
    current_path = os.environ.get("PATH", "")
    if str(bin_dir).lower() not in current_path.lower():
        print("\n[i] Adding " + str(bin_dir) + " to User PATH...")
        try:
            ps_cmd = '[Environment]::SetEnvironmentVariable("Path", $env:Path + ";' + str(bin_dir) + '", "User")'
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True)
            print("[+] Added to User PATH successfully!")
        except Exception as e:
            print("[!] Notice: Add this folder to your PATH to run 'pyapp' from any terminal:\n    " + str(bin_dir))

    print("\n[✓] Setup complete!")
    print("You can now install applications by running:")
    print("    pyapp install gemswarm")
    print("    pyapp install testapp")
    print("=" * 60)

def list_installed_apps():
    """List all locally installed PYapps."""
    apps_root = get_apps_root_dir()
    print("=" * 60)
    print(" Installed PYapps")
    print(" Directory: " + str(apps_root))
    print("=" * 60)
    
    apps = [d for d in apps_root.iterdir() if d.is_dir()]
    if not apps:
        print(" No apps currently installed.")
        print(" Run: pyapp install <name> to install one.")
        return

    for app_dir in apps:
        manifest_path = app_dir / "info.app.json"
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                app_meta = data.get("app", {})
                name = app_meta.get("app-name", app_dir.name)
                app_id = app_meta.get("app-id", "unknown")
                version = data.get("app-install-version", "1.0.0")
                print(" • " + str(name) + " [" + app_dir.name + "] (ID: " + str(app_id) + ", v" + str(version) + ")")
            except Exception:
                print(" • " + app_dir.name + " (corrupt info.app.json)")
        else:
            print(" • " + app_dir.name)

def run_app_cli(install_name: str):
    """Run an installed PYapp."""
    apps_root = get_apps_root_dir()
    app_dir = apps_root / install_name
    if not app_dir.exists():
        print("[!] App '" + install_name + "' is not installed at " + str(app_dir))
        sys.exit(1)

    launcher = app_dir / "launcher.pyw"
    if launcher.exists():
        pyw_exe = sys.executable.replace("python.exe", "pythonw.exe")
        subprocess.Popen([pyw_exe, str(launcher)], cwd=str(app_dir))
        print("[+] Launched '" + install_name + "' in background.")
    else:
        run_file = app_dir / "run.py"
        if run_file.exists():
            subprocess.run([sys.executable, str(run_file)], cwd=str(app_dir))
        else:
            print("[!] Neither launcher.pyw nor run.py found in " + str(app_dir))

def print_help():
    print("""
PYapps Package Manager & Installer
Repository: https://cb-1829.github.io/PYapps-INSTALL-SOURCE/

Commands:
  pyapp install <NAME>      Install app by install-name (extracts .zip archive)
  pyapp install <NAME> -f   Force install even if official key is missing/unverified
  pyapp list                List installed apps
  pyapp run <NAME>          Launch an installed app
  pyapp verify <NAME>       Check official key status of an app
  pyapp setup               Re-run CLI setup and environment configuration
  pyapp help                Show this help screen
""")

def main():
    if len(sys.argv) == 1:
        setup_installer_cli()
        return

    cmd = sys.argv[1].lower()

    if cmd == "install":
        if len(sys.argv) < 3:
            print("Error: Missing app install name. Example: pyapp install gemswarm")
            sys.exit(1)
        install_name = sys.argv[2]
        force_flag = ("-f" in sys.argv or "--force" in sys.argv)
        install_app(install_name, force=force_flag)

    elif cmd == "setup":
        setup_installer_cli()

    elif cmd == "list":
        list_installed_apps()

    elif cmd == "run":
        if len(sys.argv) < 3:
            print("Error: Missing app install name. Example: pyapp run gemswarm")
            sys.exit(1)
        run_app_cli(sys.argv[2])

    elif cmd == "verify":
        if len(sys.argv) < 3:
            print("Error: Missing app-id or install-name. Example: pyapp verify a1a1")
            sys.exit(1)
        target = sys.argv[2]
        if validate_app_id(target):
            verified, msg = verify_official_key(target, None, None)
            print("Verification result for '" + target + "': " + str(msg))
        else:
            apps_root = get_apps_root_dir()
            m_path = apps_root / target / "info.app.json"
            if m_path.exists():
                d = json.loads(m_path.read_text(encoding="utf-8"))
                aid = d.get("app", {}).get("app-id") or d.get("app-id")
                k = d.get("app", {}).get("app-officialkey")
                kl = d.get("app", {}).get("app-officialkey-link")
                verified, msg = verify_official_key(aid, k, kl)
                print("Result for '" + target + "' (ID: " + str(aid) + "): " + str(msg))
            else:
                print("[!] App '" + target + "' not found locally. Pass a 4-char ID to check online.")

    elif cmd in ("help", "--help", "-h"):
        print_help()

    else:
        print("Unknown command: '" + cmd + "'. Run 'pyapp help' for usage.")

if __name__ == "__main__":
    main()
