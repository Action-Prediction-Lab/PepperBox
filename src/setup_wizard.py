#!/usr/bin/env python3
import os
import shutil
import sys
from unittest.mock import patch

from qibullet import tools

LICENCE_ENV = "PEPPERBOX_ACCEPT_SOFTBANK_LICENSE"
LICENCE_NOTE = """\
qibullet's first-time setup installs SoftBank Robotics' Pepper URDF and mesh
assets, which are distributed under SoftBank Robotics' end-user licence (see
the LICENSE-* files bundled with the qibullet package).

To proceed, acknowledge the licence by exporting:

  export {env}=1

Then re-run this script (or restart the container; the entrypoint will pick
it up automatically).
""".format(env=LICENCE_ENV)


def licence_accepted() -> bool:
    return os.environ.get(LICENCE_ENV, "").lower() in {"1", "true", "yes"}


def setup():
    print("=" * 60)
    print("      PepperBox Setup Wizard (qibullet)")
    print("=" * 60)

    if not licence_accepted():
        print(LICENCE_NOTE)
        sys.exit(1)

    qibullet_root = os.path.join(os.path.expanduser("~"), ".qibullet")
    print(f"Checking {qibullet_root}...")
    if os.path.exists(qibullet_root):
        print("Found existing qibullet folder (docker volume); clearing for fresh install...")
        try:
            for filename in os.listdir(qibullet_root):
                file_path = os.path.join(qibullet_root, filename)
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            print("Cleanup complete.")
        except Exception as e:
            print(f"Warning: could not clean folder: {e}")

    print(f"Licence acknowledged via {LICENCE_ENV}=1; proceeding.")
    print("-" * 60)

    original_mkdir = os.mkdir

    def safe_mkdir(path, *args, **kwargs):
        try:
            original_mkdir(path, *args, **kwargs)
        except FileExistsError:
            pass

    try:
        # qibullet's installer interactively prompts for licence acceptance
        # and tries to delete its install directory before re-creating it. The
        # docker-mounted .qibullet path can't be deleted from inside the
        # container, so we mock the relevant calls. The licence prompt is
        # already gated above by the env var, so the inner mock is just
        # plumbing to satisfy the installer.
        with patch("builtins.input", return_value="y"), \
             patch("qibullet.tools._uninstall_resources", return_value=True), \
             patch("os.mkdir", side_effect=safe_mkdir):

            print("Invoking qibullet installer...")
            tools._install_resources()

        print("\n" + "=" * 60)
        print("SUCCESS — qibullet assets installed.")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\nSetup cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nError during setup: {e}")
        sys.exit(1)


if __name__ == "__main__":
    setup()
