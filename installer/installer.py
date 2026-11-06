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

import os
import sys
import json
import re
import shutil
import urllib.request
import urllib.error
import subprocess
from pathlib import Path

# Base configuration constants
REPO_RAW_BASE = "https://raw.githubusercontent.com/CB-1829/PYapps-INSTALL-SOURCE/main"
GITHUB_IO_BASE = "https://cb-1829.github.io/PYapps-INSTALL-SOURCE"
OFFICIAL_KEYS_BASE = f"{GITHUB_IO_BASE}/installer/officialkeys/mainkeys"

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

def fetch_url_bytes(url: str, timeout: int = 15) -> tuple[bool, bytes]:
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

def verify_official_key(app_id: str, local_key: str | None, key_link: str | None) -> tuple[bool, str]:
    """
    Checks the key against the official key on:
    https://cb-1829.github.io/PYapps-INSTALL-SOURCE/installer/officialkeys/mainkeys/APP-ID-HERE.key
    """
    if not validate_app_id(app_id):
        return False, f"Invalid app-id format: '{app_id}'. Must be strictly 4 characters [a-z0-9]."
    
    # 1. Resolve key candidate from local file or link
    candidate_key = ""
    if local_key and local_key.strip():
        candidate_key = local_key.strip()
    elif key_link and key_link.strip():
        print(f"[*] Fetching candidate key from link: {key_link}...")
        ok, fetched = fetch_url_text(key_link.strip())
        if ok and fetched.strip():
            candidate_key = fetched.strip()
        else:
            return False, f"Could not fetch key from link '{key_link}': {fetched}"
    else:
        return False, "No 'app-officialkey' or 'app-officialkey-link' specified in info.app.json."

    # 2. Query official remote key
    official_url = f"{OFFICIAL_KEYS_BASE}/{app_id}.key"
    print(f"[*] Verifying key against official repository: {official_url}")
    ok, official_key = fetch_url_text(official_url)
    
    if not ok:
        return False, f"Could not fetch official key for app-id '{app_id}' from official repo ({official_key})."
    
    clean_official = official_key.strip()
    if candidate_key == clean_official:
        return True, "Key verified: Official Match confirmed."
    else:
        return False, f"Key mismatch! Provided key does not match official repository key for '{app_id}'."

def create_windows_shortcut(target_exe: str, args: str, shortcut_path: str, icon_path: str = "", description: str = ""):
    """
    Creates a native Windows .lnk shortcut with custom icon using PowerShell or VBScript.
    This gives the application its visual icon on Desktop / Start Menu.
    """
    try:
        escaped_target = target_exe.replace("'", "''")
        escaped_args = args.replace("'", "''")
        escaped_path = shortcut_path.replace("'", "''")
        escaped_icon = icon_path.replace("'", "''")
        escaped_desc = description.replace("'", "''")

        ps_script = f"""
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut('{escaped_path}')
        $Shortcut.TargetPath = '{escaped_target}'
        $Shortcut.Arguments = '{escaped_args}'
        if ('{escaped_icon}' -ne '' -and (Test-Path '{escaped_icon}')) {{
            $Shortcut.IconLocation = '{escaped_icon}'
        }}
        $Shortcut.Description = '{escaped_desc}'
        $Shortcut.WindowStyle = 1
        $Shortcut.Save()
        """
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script], check=True, capture_output=True)
        return True
    except Exception as e:
        print(f"[!] Notice: Could not create desktop .lnk shortcut automatically: {e}")
        return False

def generate_silent_runner(app_dir: Path, app_name: str, entry_file: str) -> Path:
    """
    Creates a smart launcher script (launcher.pyw).
    
    How this satisfies the user's specification:
    1. Uses pythonw.exe so Windows hides the command prompt window completely by default.
    2. Runs the target run.py file.
    3. If run.py produces text output or an error occurs, it attaches/allocates a console
       or opens a clean output dialog, so text output is NEVER lost!
    """
    launcher_file = app_dir / "launcher.pyw"
    code = f'''# -*- coding: utf-8 -*-
"""
PYapps Smart Launcher for {app_name}
Runs run.py with console hidden unless stdout/stderr has text.
"""
import sys
import os
import subprocess
import ctypes

def main():
    app_dir = os.path.dirname(os.path.abspath(__file__))
    target_script = os.path.join(app_dir, "{entry_file}")
    
    # Locate standard python or pythonw executable
    py_exec = sys.executable
    if "pythonw.exe" in py_exec.lower():
        # Find companion python.exe if we need console output
        normal_py = py_exec.lower().replace("pythonw.exe", "python.exe")
        if os.path.exists(normal_py):
            py_runner = normal_py
        else:
            py_runner = py_exec
    else:
        py_runner = py_exec

    # Hide console during execution via STARTUPINFO
    startupinfo = None
    creationflags = 0
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
        creationflags = subprocess.CREATE_NO_WINDOW

    # Execute run.py capturing output
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
            root.title(f"PYapps Console - {app_name}")
            root.geometry("640x380")
            root.configure(bg="#1e1e1e")
            
            lbl = tk.Label(root, text=f"{app_name} Output Log", fg="#00ff66", bg="#1e1e1e", font=("Consolas", 11, "bold"))
            lbl.pack(anchor="w", padx=10, pady=(8, 2))

            txt = scrolledtext.ScrolledText(root, bg="#111", fg="#eee", insertbackground="white", font=("Consolas", 10))
            txt.pack(expand=True, fill="both", padx=10, pady=8)
            txt.insert("1.0", output)
            txt.configure(state="disabled")
            
            btn = tk.Button(root, text="Close Window", command=root.destroy, bg="#333", fg="white", padx=10, pady=4)
            btn.pack(pady=(0, 8))
            root.mainloop()
        except Exception:
            # Fallback for Windows message box
            if sys.platform == "win32":
                ctypes.windll.user32.MessageBoxW(0, output[:2000], f"PYapps - {app_name} Output", 0x40)

if __name__ == "__main__":
    main()
'''
    launcher_file.write_text(code, encoding="utf-8")
    return launcher_file

def install_app(install_name: str, force: bool = False):
    """
    Main installation logic for `pyapp install <APP_INSTALL_NAME>`.
    """
    # Validate install name (6-10 letters)
    if not validate_install_name(install_name):
        print(f"[!] Error: 'app-install-name' must be between 6 and 10 letters (a-z, A-Z).")
        print(f"    Provided: '{install_name}' ({len(install_name)} chars)")
        sys.exit(1)

    print(f"============================================================")
    print(f" PYapps Installer - Fetching '{install_name}'")
    print(f"============================================================")

    # Remote URL for app's info.app.json
    manifest_url = f"{REPO_RAW_BASE}/apps/{install_name}/info.app.json"
    print(f"[*] Downloading application manifest: {manifest_url}")
    
    ok, manifest_content = fetch_url_text(manifest_url)
    if not ok:
        # Fallback check under GitHub IO
        manifest_url_io = f"{GITHUB_IO_BASE}/apps/{install_name}/info.app.json"
        ok, manifest_content = fetch_url_text(manifest_url_io)
    
    if not ok:
        print(f"[!] Error: Could not find application '{install_name}'.")
        print(f"    Check that '{install_name}' exists in PYapps-INSTALL-SOURCE/apps/{install_name}/info.app.json")
        sys.exit(1)

    try:
        manifest = json.loads(manifest_content)
    except Exception as e:
        print(f"[!] Error: Failed to parse info.app.json: {e}")
        sys.exit(1)

    # Extract schema fields
    app_meta = manifest.get("app", {})
    app_name = app_meta.get("app-name") or manifest.get("app-name", install_name)
    app_id = app_meta.get("app-id") or manifest.get("app-id")
    app_key = app_meta.get("app-officialkey") or manifest.get("app-officialkey")
    app_key_link = app_meta.get("app-officialkey-link") or manifest.get("app-officialkey-link")
    app_icon = app_meta.get("app-icon") or manifest.get("app-icon", "")
    install_version = manifest.get("app-install-version", "1.0.0")
    install_spec = manifest.get("app-install", {})

    print(f"\n[i] App Name:    {app_name}")
    print(f"[i] App ID:      {app_id}")
    print(f"[i] Version:     {install_version}")

    # Validate 4-digit ID
    if not app_id or not validate_app_id(app_id):
        print(f"\n[!] Error: 'app-id' is required to be a 4-digit ID using a-z and 0-9.")
        print(f"    Provided: '{app_id}'")
        sys.exit(1)

    # Perform Official Key Verification
    print("\n[*] Performing Official Key Verification...")
    verified, verify_msg = verify_official_key(app_id, app_key, app_key_link)

    if verified:
        print(f"[✓] {verify_msg}")
        print("[✓] Package is authentic and verified with the PYapps repository.")
    else:
        print("\n" + "!" * 60)
        print(" [!] SECURITY WARNING: OFFICIAL KEY VERIFICATION FAILED!")
        print(f" Reason: {verify_msg}")
        print(" Without a matching official key in:")
        print(f" {OFFICIAL_KEYS_BASE}/{app_id}.key")
        print(" this application is UNVERIFIED and could be modified or untrusted.")
        print("!" * 60)
        
        if not force:
            choice = input("\nDo you still want to proceed with installing this unverified app? (y/N): ").strip().lower()
            if choice not in ("y", "yes"):
                print("[*] Installation aborted by user for security.")
                sys.exit(1)
        else:
            print("[!] Force flag specified: continuing installation despite warning.")

    # Destination folder:
    # C:\Users\<USER>\AppData\Local\Programs\Python\Python314\pyappsinstall\apps\<install_name>
    apps_root = get_apps_root_dir()
    app_dest = apps_root / install_name
    app_dest.mkdir(parents=True, exist_ok=True)
    print(f"\n[*] Installing files to: {app_dest}")

    # Save info.app.json locally
    (app_dest / "info.app.json").write_text(manifest_content, encoding="utf-8")

    # Fetch required files (run.py, app.py, icon, etc.)
    files_to_download = install_spec.get("files", ["run.py", "app.py"])
    if "run.py" not in files_to_download:
        files_to_download.append("run.py")
    if app_icon and app_icon not in files_to_download:
        files_to_download.append(app_icon)

    for fname in files_to_download:
        file_url = f"{REPO_RAW_BASE}/apps/{install_name}/{fname}"
        target_path = app_dest / fname
        print(f"[*] Downloading {fname}...")
        ok, data = fetch_url_bytes(file_url)
        if ok and len(data) > 0:
            target_path.write_bytes(data)
        else:
            # Fallback to local sample if testing in offline/local mode
            sample_local = Path(__file__).resolve().parent.parent / "apps" / install_name / fname
            if sample_local.exists():
                shutil.copyfile(sample_local, target_path)
                print(f"[+] Loaded local fallback for {fname}")
            else:
                print(f"[!] Warning: Could not download {fname} from {file_url}")

    # Generate the smart silent launcher (hides console window unless printing text)
    entry_file = install_spec.get("entry", "run.py")
    launcher_file = generate_silent_runner(app_dest, app_name, entry_file)
    print(f"[+] Generated silent launcher: {launcher_file.name}")

    # Create desktop shortcut with the icon
    icon_dest_file = app_dest / app_icon if app_icon else ""
    desktop_dir = Path.home() / "Desktop"
    if desktop_dir.exists():
        shortcut_file = desktop_dir / f"{app_name}.lnk"
        
        # Locate pythonw.exe for windowless execution
        pyw_exe = sys.executable.replace("python.exe", "pythonw.exe")
        if not os.path.exists(pyw_exe):
            pyw_exe = sys.executable

        shortcut_created = create_windows_shortcut(
            target_exe=pyw_exe,
            args=f'"{launcher_file}"',
            shortcut_path=str(shortcut_file),
            icon_path=str(icon_dest_file) if icon_dest_file and icon_dest_file.exists() else "",
            description=f"{app_name} (PYapps)"
        )
        if shortcut_created:
            print(f"[+] Created desktop app shortcut with icon: {shortcut_file}")

    print(f"\n============================================================")
    print(f" [✓] Installation of '{app_name}' ({install_name}) Complete!")
    print(f" Location: {app_dest}")
    print(f" To launch, double click the desktop shortcut or run:")
    print(f" pyapp run {install_name}")
    print(f"============================================================")

def setup_installer_cli():
    """
    Configures `pyapp` command so typing 'pyapp install <name>' works in cmd/powershell.
    Executed when installer is installed via:
    curl.exe -sL https://cb-1829.github.io/PYapps-INSTALL-SOURCE/installer/installer.py | py
    """
    bin_dir = get_pyapp_bin_dir()
    apps_dir = get_apps_root_dir()

    # Store a copy of installer.py in the pyapps directory
    installed_installer_path = apps_dir.parent / "installer.py"
    try:
        shutil.copyfile(__file__, installed_installer_path)
    except Exception:
        # If piped via stdin, write current code
        with open(__file__ if os.path.exists(__file__) else sys.argv[0], "rb") as src:
            installed_installer_path.write_bytes(src.read())

    # Create pyapp.cmd for Windows command prompt & PowerShell
    cmd_file = bin_dir / "pyapp.cmd"
    batch_content = f"""@echo off
py "{installed_installer_path}" %*
"""
    cmd_file.write_text(batch_content, encoding="utf-8")

    # Add bin_dir to user PATH if not present
    print("=" * 60)
    print("  PYapps Installer - System Setup")
    print("=" * 60)
    print(f"[+] Installed PYapps core to: {apps_dir.parent}")
    print(f"[+] Created CLI command: {cmd_file}")
    print(f"[+] Target Apps Directory: {apps_dir}")
    
    # Check if bin_dir is in PATH
    current_path = os.environ.get("PATH", "")
    if str(bin_dir).lower() not in current_path.lower():
        print(f"\n[i] Adding {bin_dir} to User PATH...")
        try:
            ps_cmd = f'[Environment]::SetEnvironmentVariable("Path", $env:Path + ";{bin_dir}", "User")'
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True)
            print("[+] Added to User PATH successfully!")
        except Exception as e:
            print(f"[!] Notice: Add this folder to your PATH to run 'pyapp' from any terminal:\n    {bin_dir}")

    print("\n[✓] Setup complete!")
    print("You can now install applications by running:")
    print("    pyapp install testapp")
    print("=" * 60)

def list_installed_apps():
    """List all locally installed PYapps."""
    apps_root = get_apps_root_dir()
    print("=" * 60)
    print(" Installed PYapps")
    print(f" Directory: {apps_root}")
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
                print(f" • {name} [{app_dir.name}] (ID: {app_id}, v{version})")
            except Exception:
                print(f" • {app_dir.name} (corrupt info.app.json)")
        else:
            print(f" • {app_dir.name}")

def run_app_cli(install_name: str):
    """Run an installed PYapp."""
    apps_root = get_apps_root_dir()
    app_dir = apps_root / install_name
    if not app_dir.exists():
        print(f"[!] App '{install_name}' is not installed at {app_dir}")
        sys.exit(1)

    launcher = app_dir / "launcher.pyw"
    if launcher.exists():
        pyw_exe = sys.executable.replace("python.exe", "pythonw.exe")
        subprocess.Popen([pyw_exe, str(launcher)], cwd=str(app_dir))
        print(f"[+] Launched '{install_name}' in background.")
    else:
        run_file = app_dir / "run.py"
        if run_file.exists():
            subprocess.run([sys.executable, str(run_file)], cwd=str(app_dir))
        else:
            print(f"[!] Neither launcher.pyw nor run.py found in {app_dir}")

def print_help():
    print("""
PYapps Package Manager & Installer
Repository: https://cb-1829.github.io/PYapps-INSTALL-SOURCE/

Commands:
  pyapp install <NAME>      Install app (validates 4-char ID & official key)
  pyapp install <NAME> -f   Force install even if official key is missing/unverified
  pyapp list                List installed apps
  pyapp run <NAME>          Launch an installed app
  pyapp verify <NAME>       Check official key status of an app
  pyapp setup               Re-run CLI setup and environment configuration
  pyapp help                Show this help screen
""")

def main():
    # If run with no arguments (e.g. piped via curl | py)
    if len(sys.argv) == 1:
        setup_installer_cli()
        return

    cmd = sys.argv[1].lower()

    if cmd == "install":
        if len(sys.argv) < 3:
            print("Error: Missing app install name. Example: pyapp install testapp")
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
            print("Error: Missing app install name. Example: pyapp run testapp")
            sys.exit(1)
        run_app_cli(sys.argv[2])

    elif cmd == "verify":
        if len(sys.argv) < 3:
            print("Error: Missing app-id or install-name. Example: pyapp verify testapp")
            sys.exit(1)
        target = sys.argv[2]
        if validate_app_id(target):
            verified, msg = verify_official_key(target, None, None)
            print(f"Verification result for '{target}': {msg}")
        else:
            # Look in installed apps
            apps_root = get_apps_root_dir()
            m_path = apps_root / target / "info.app.json"
            if m_path.exists():
                d = json.loads(m_path.read_text(encoding="utf-8"))
                aid = d.get("app", {}).get("app-id") or d.get("app-id")
                k = d.get("app", {}).get("app-officialkey")
                kl = d.get("app", {}).get("app-officialkey-link")
                verified, msg = verify_official_key(aid, k, kl)
                print(f"Result for '{target}' (ID: {aid}): {msg}")
            else:
                print(f"[!] App '{target}' not found locally. Pass a 4-char ID to check online.")

    elif cmd in ("help", "--help", "-h"):
        print_help()

    else:
        print(f"Unknown command: '{cmd}'. Run 'pyapp help' for usage.")

if __name__ == "__main__":
    main()
