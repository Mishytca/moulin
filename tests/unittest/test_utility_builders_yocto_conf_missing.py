import unittest
from unittest.mock import patch, Mock
import moulin.builders.yocto as yocto_mod


class TestYoctoUtilityConfMissing(unittest.TestCase):
    def test_stamp_exists_conf_folder_missing(self):
        """
        it is assumed that the conf folder is deleted or inaccessible.
        Stamp exists, but bblayers.conf effectively resets to defaults (only 3 poky layers).
        Expected:
          - _run_bash called with 'bitbake-layers show-layers'
          - sync_layers() runs:
              -- bitbake-layers remove-layer  || true   (empty list safe)
              -- bitbake-layers add-layer <desired from argv>
              -- and finally creates the stamp file with touch
        """
        # create variables needed for the test
        yocto_dir = "/abs/path/to/yocto"
        work_dir = "build-dom0"
        layers = ["../fake-layer1", "../fake-layer2"]
        stamp_path = "/tmp/layers.stamp"

        show_layers_stdout = (
            "layer  path                     priority\n"
            "========================================\n"
            "meta   /abs/poky/meta           7\n"
            "meta   /abs/poky/meta-poky      5\n"
            "meta   /abs/poky/meta-yocto-bsp 5\n"
        )

        with patch("moulin.builders.yocto.Path.exists", return_value=True), \
             patch("moulin.builders.yocto._run_bash") as mock_run, \
             patch("moulin.builders.yocto.subprocess.run") as mock_subproc:

            # _run_bash simulates returning show-layers output
            mock_run.return_value = Mock(returncode=0, stdout=show_layers_stdout, stderr="")
            # subprocess.run should don't actually run shell
            mock_subproc.return_value = None

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
        show_cmd = mock_run.call_args[0][0]

        # _run_bash called with 'bitbake-layers show-layers'
        self.assertIn("bitbake-layers show-layers", show_cmd)

        # cmd contains oe-init-build-env and work_dir
        self.assertIn(f"cd {yocto_dir}", show_cmd)
        self.assertIn("oe-init-build-env", show_cmd)

        # sync_layers() -> check the compiled shell command
        self.assertIsNotNone(mock_subproc.call_args)
        bash_argv = mock_subproc.call_args[0][0]
        self.assertEqual(bash_argv[:2], ["bash", "-lc"])
        sync_cmd = bash_argv[2]

        # remove empty list + add required layers + touch
        self.assertIn("bitbake-layers remove-layer  || true", sync_cmd)
        self.assertIn("bitbake-layers add-layer", sync_cmd)
        for layer in layers:
            self.assertIn(layer, sync_cmd)
        self.assertIn(f"touch {stamp_path}", sync_cmd)
