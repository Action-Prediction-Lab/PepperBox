#!/usr/bin/env python3
import sys
import os
import shutil
from unittest.mock import patch
from qibullet import SimulationManager
from qibullet import PepperVirtual
from qibullet import tools

def setup():
    print("="*60)
    print("      PepperBox Setup Wizard (qibullet)")
    print("="*60)
    
    # 1. Force Clean Check
    qibullet_root = os.path.join(os.path.expanduser("~"), ".qibullet")
    print(f"Checking {qibullet_root}...")
    if os.path.exists(qibullet_root):
        print(f"Found existing qibullet folder (Docker Volume).")
        print("Cleaning contents to force fresh install...")
        try:
            for filename in os.listdir(qibullet_root):
                file_path = os.path.join(qibullet_root, filename)
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            print("Cleanup complete.")
        except Exception as e:
            print(f"Warning: Could not clean folder: {e}")

    print("Refusing to launch GUI to ensure clean asset installation.")
    print("Auto-accepting Softbank Robotics license...")
    print("-" * 60)
    
    # Custom mkdir that ignores "File exists" errors
    original_mkdir = os.mkdir
    def safe_mkdir(path, *args, **kwargs):
        try:
            original_mkdir(path, *args, **kwargs)
        except FileExistsError:
            pass

    try:
        # MOCK 1: Input -> 'y' (Accept license)
        # MOCK 2: _uninstall_resources -> True (Don't try to delete the Docker mount point)
        # MOCK 3: os.mkdir -> safe_mkdir (Allow existing folders/volumes)
        with patch('builtins.input', return_value='y'), \
             patch('qibullet.tools._uninstall_resources', return_value=True), \
             patch('os.mkdir', side_effect=safe_mkdir):
             
             print("Invoking installer with auto-accept...")
             tools._install_resources()
        
        print("\n\n" + "="*60)
        print("SUCCESS! Assets installed.")
        print(" you can now run 'python3 qibullet_shim_server.py'")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\nSetup cancelled by user.")
    except Exception as e:
        print(f"\nError during setup: {e}")

if __name__ == "__main__":
    setup()
