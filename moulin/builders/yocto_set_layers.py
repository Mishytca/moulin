import argparse
import shlex
import subprocess
import logging
import os
from pathlib import Path
from typing import List

log = logging.getLogger(__name__)


def _env_prefix(yocto_dir: str, work_dir: str) -> str:
    """
    Return a shell snippet that cd's into yocto_dir and sources
    oe-init-build-env for work_dir.
    """
    return " && ".join([
        f"cd {shlex.quote(yocto_dir)}",
        f". poky/oe-init-build-env {shlex.quote(work_dir)}",  # баннер пусть остаётся
    ])


def _run_bash(cmd: str, *, capture=False) -> subprocess.CompletedProcess:
    """Run a bash -lc command."""
    return subprocess.run(
        ["bash", "-lc", cmd],
        check=True,
        capture_output=capture,
        text=capture,
    )


def handle_utility_call(conf, argv: List[str]) -> int:
    """
    Minimal utility to sync Yocto layers:
    - If no stamp: add desired layers and create stamp.
    - If stamp exists: read current layers, normalize to relative paths, compare,
    and if different: remove current + add desired + touch stamp.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--yocto-dir", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--layers", nargs="+", required=True)
    parser.add_argument("--stamp", required=True)
    args = parser.parse_args(argv)

    layers_str = " ".join(shlex.quote(x) for x in args.layers)
    stamp_out = shlex.quote(args.stamp)
    stamp_exists = Path(args.stamp).exists()
    env_prefix = _env_prefix(args.yocto_dir, args.work_dir)

    def sync_layers():
        """Remove current layers and add desired ones; then touch the stamp."""
        cmd = (
            f"{env_prefix} && "
            f"( bitbake-layers remove-layer {rel_paths_str} || true ) && "
            f"bitbake-layers add-layer {layers_str} && "
            f"touch {stamp_out}"
        )
        subprocess.run(["bash", "-lc", cmd], check=True)

    # no stamp --> add layers and create the stamp
    if not stamp_exists:
        _run_bash(f"{env_prefix} && bitbake-layers add-layer {layers_str} && touch {stamp_out}")
    else:
        # stamp exists, then we show and parse the show-layers
        show = _run_bash(f"{env_prefix} && bitbake-layers show-layers", capture=True).stdout

        # Parse the table
        lines = show.splitlines()

        start = None
        for i, line in enumerate(lines):
            if line.strip().startswith("layer") and "path" in line and "priority" in line:
                start = i
                break

        # Output only table
        if start is not None:
            table_lines = lines[start:]
            # Take the second column (paths)
            paths_only = []
            for ln in table_lines[2:]:  # skip the header and "====="
                s = ln.strip()
                if not s or set(s) == {"="}:
                    continue
                parts = s.split()
                if len(parts) >= 2:
                    paths_only.append(parts[1])
        else:
            print("Couldn't find table in show-layers output")

        # 1) Canonicalize (absolute paths, unfold ~, normalize..)
        canonical_paths = [str(Path(p).expanduser().resolve(strict=False)) for p in paths_only]

        # 2) Compute BUILDDIR absolute path (base for relative layer paths)
        work_dir_path = Path(args.work_dir)
        build_abs = (work_dir_path if work_dir_path.is_absolute()
                     else (Path(args.yocto_dir) / work_dir_path)).resolve(strict=False)

        # 3) Discard the first 3 layers (poky/meta, meta-poky, meta-yocto-bsp)
        rest = canonical_paths[3:] if len(canonical_paths) > 3 else []

        # 4) Recalculate to relative paths from build_abs
        rel_paths = [os.path.relpath(p, start=str(build_abs)) for p in rest]
        rel_paths_str = " ".join(shlex.quote(p) for p in rel_paths)

        # 5) If the number of elements is different, sync_layers immediately
        if len(args.layers) != len(rel_paths):
            sync_layers()
        else:
            # 6) The quantity is the same --> compare the contents (taking into account the order)
            desired_rel = [os.path.normpath(p) for p in args.layers]
            current_rel = [os.path.normpath(p) for p in rel_paths]
            if desired_rel != current_rel:
                sync_layers()
            else:
                print("Layers already in sync; nothing to do.")
    return 0
