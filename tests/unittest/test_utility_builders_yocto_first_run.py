import unittest
from unittest.mock import patch, Mock
import moulin.builders.yocto as yocto_mod


class TestYoctoUtilityFirstRun(unittest.TestCase):
    def test_first_run_no_stamp_calls_add_layer(self):
        """
        Test the 'first run' scenario of handle_utility_call:
        - Stamp file does not exist (Path.exists -> False).
        - Function must call _run_bash with a command that:
            -- changes into the Yocto directory,
            -- sources oe-init-build-env with the given work_dir,
            -- runs 'bitbake-layers add-layer' for all layers,
            -- does NOT run 'bitbake-layers show-layers',
            -- and finally creates the stamp file with touch.
        """
        # create variables needed for the test
        yocto_dir = "/abs/path/to/yocto"
        work_dir = "build-dom0"
        layers = ["../fake-layer1", "../fake-layer2"]
        stamp_path = "/tmp/layers.stamp"

        with patch("moulin.builders.yocto.Path.exists", return_value=False), \
             patch("moulin.builders.yocto._run_bash") as mock_run:

            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            yocto_mod.handle_utility_call(
                conf=None,
                argv=[
                    "--yocto-dir", yocto_dir,
                    "--work-dir", work_dir,
                    "--layers", *layers,
                    "--stamp", stamp_path,
                ],
            )

        # check command is not None
        self.assertIsNotNone(mock_run.call_args)

        # take the command passed to _run_bash
        cmd = mock_run.call_args[0][0]

        # check command contents
        # cmd contains cd to /abs/path/to/yocto
        self.assertIn(f"cd {yocto_dir}", cmd)

        # cmd contains oe-init-build-env and work_dir
        self.assertIn("oe-init-build-env", cmd)
        self.assertIn(work_dir, cmd)

        # cmd contains bitbake-layers add-layer and var layers
        self.assertIn("bitbake-layers add-layer", cmd)
        for layer in layers:
            self.assertIn(layer, cmd)

        # cmd no contains bitbake-layers show-layers
        self.assertNotIn("bitbake-layers show-layers", cmd)

        # cmd no contains stamp_path
        self.assertIn(f"touch {stamp_path}", cmd)
