import argparse
import shlex
import subprocess
import logging
from typing import List

log = logging.getLogger(__name__)


def handle_utility_call(conf, argv: List[str]) -> int:

    print("[yocto_set_layers] raw argv:", repr(argv))

    parser = argparse.ArgumentParser(prog="--utility-builders-yocto-set-layers", add_help=False)
    parser.add_argument("--yocto-dir", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--set-layers", nargs="+", required=True)
    args = parser.parse_args(argv)

    print("[yocto_set_layers] yocto_dir:", args.yocto_dir)
    print("[yocto_set_layers] work_dir:", args.work_dir)
    print("[yocto_set_layers] set_layers:", args.set_layers)

    # Quote layer paths to avoid word splitting
    layers = " ".join(shlex.quote(x) for x in args.set_layers)

    # Build one bash -lc script for a clean env with `set -e`
    bash_script = " && ".join([
        f"cd {shlex.quote(args.yocto_dir)}",
        f". poky/oe-init-build-env {shlex.quote(args.work_dir)} >/dev/null",
        f"bitbake-layers add-layer {layers}",
    ])

    log.debug("yocto_set_layers: running bash -lc: %s", bash_script)

    try:
        subprocess.run(["bash", "-lc", bash_script], check=True)
    except subprocess.CalledProcessError as e:
        log.error("yocto_set_layers failed with code %s", e.returncode)
        return e.returncode

    return 0


# Optional fallback entry to support both handler names
def main(conf, argv: List[str]) -> int:
    return handle_utility_call(conf, argv)
