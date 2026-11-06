#!/usr/bin/env python3
"""
PYapps Official Key Finder & Validator
Part of PYapps-INSTALL-SOURCE ecosystem
Path: installer/officialkeys/keyfinderfiles/finder.py
"""

import os
import sys
import json
import re
import hashlib
import secrets
import urllib.request
import urllib.error

OFFICIAL_KEY_BASE_URL = "https://cb-1829.github.io/PYapps-INSTALL-SOURCE/installer/officialkeys/mainkeys"

def validate_app_id(app_id: str) -> bool:
    """Validate that app-id is strictly 4 characters containing only a-z and 0-9."""
    return bool(re.fullmatch(r"^[a-z0-9]{4}$", app_id))

def generate_key_for_app(app_id: str, app_install_name: str) -> str:
    """Generate a secure cryptographic official key hash for an app."""
    if not validate_app_id(app_id):
        raise ValueError(f"Invalid app-id '{app_id}'. Must be 4 characters [a-z0-9].")
    entropy = secrets.token_hex(16)
    payload = f"{app_id}:{app_install_name}:{entropy}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def fetch_remote_key(app_id: str) -> tuple[bool, str]:
    """Fetch the official key for an app-id from the official GitHub repository."""
    if not validate_app_id(app_id):
        return False, f"Invalid app-id '{app_id}'"
    
    key_url = f"{OFFICIAL_KEY_BASE_URL}/{app_id}.key"
    try:
        req = urllib.request.Request(
            key_url,
            headers={"User-Agent": "PYapps-Finder/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            key_content = response.read().decode("utf-8").strip()
            return True, key_content
    except urllib.error.HTTPError as e:
        return False, f"HTTP Error {e.code}: Key not found on remote server"
    except Exception as e:
        return False, f"Failed to fetch key: {str(e)}"

def verify_app_key(app_id: str, local_key: str) -> tuple[bool, str]:
    """Compare a local key with the official online key."""
    success, remote_key = fetch_remote_key(app_id)
    if not success:
        return False, f"Remote check failed: {remote_key}"
    
    clean_local = local_key.strip()
    clean_remote = remote_key.strip()
    
    if clean_local == clean_remote:
        return True, "Key verified: Official Match"
    else:
        return False, "Key mismatch: Local key does not match official key"

def main():
    print("=" * 60)
    print("  PYapps Official Key Finder & Validator")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python finder.py check <app_id> [local_key]")
        print("  python finder.py generate <app_id> <app_install_name>")
        print("  python finder.py validate-id <app_id>")
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "validate-id":
        if len(sys.argv) < 3:
            print("Error: Missing app-id")
            sys.exit(1)
        app_id = sys.argv[2]
        is_valid = validate_app_id(app_id)
        print(f"App ID '{app_id}' is {'VALID' if is_valid else 'INVALID (must be 4 chars [a-z0-9])'}")

    elif cmd == "check":
        if len(sys.argv) < 3:
            print("Error: Missing app-id")
            sys.exit(1)
        app_id = sys.argv[2]
        local_key = sys.argv[3] if len(sys.argv) > 3 else None
        
        print(f"[*] Querying official key for app-id: {app_id}...")
        ok, res = fetch_remote_key(app_id)
        if ok:
            print(f"[+] Found official remote key: {res}")
            if local_key:
                matches = (local_key.strip() == res.strip())
                if matches:
                    print("[✓] LOCAL KEY VERIFIED AGAINST OFFICIAL REPO!")
                else:
                    print("[!] WARNING: LOCAL KEY DOES NOT MATCH OFFICIAL KEY!")
        else:
            print(f"[-] {res}")

    elif cmd == "generate":
        if len(sys.argv) < 4:
            print("Error: Usage: python finder.py generate <app_id> <app_install_name>")
            sys.exit(1)
        app_id = sys.argv[2]
        install_name = sys.argv[3]
        if not validate_app_id(app_id):
            print(f"Error: app-id must be 4 characters (a-z, 0-9). Got: '{app_id}'")
            sys.exit(1)
        
        key = generate_key_for_app(app_id, install_name)
        print(f"[+] Generated official key for app '{install_name}' ({app_id}):")
        print(key)
        print(f"\nSave this content to: installer/officialkeys/mainkeys/{app_id}.key")

if __name__ == "__main__":
    main()
