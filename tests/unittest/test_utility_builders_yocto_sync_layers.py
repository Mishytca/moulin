import unittest
from unittest.mock import patch, Mock
import moulin.builders.yocto as yocto_mod


class TestYoctoUtilitySyncLayers(unittest.TestCase):
    def test_stamp_exists_sync_layers(self):
        """
        Stamp exists, but current layers (from `show-layers`) differ from desired `argv`.
        Expected:
          - '_run_bash' is called with 'bitbake-layers show-layers'
          - then sync_layers() is triggered via `subprocess.run`:
              -- bitbake-layers remove-layer <...> || true
              -- bitbake-layers add-layer <desired from argv>
              -- touch <stamp>
        """
        # create variables needed for the test
        yocto_dir = "/abs/path/to/yocto"
        work_dir = "build-dom0"
        layers = ["../fake-layer1", "../fake-layer2"]
        stamp_path = "/tmp/layers.stamp"

        # show-layers returns default 3 + one "current" layer (different from desired)
        show_layers_stdout = (
            "layer  path                     priority\n"
            "========================================\n"
            "meta   /abs/poky/meta           7\n"
            "meta   /abs/poky/meta-poky      5\n"
            "meta   /abs/poky/meta-yocto-bsp 5\n"
            f"meta   {yocto_dir}/{work_dir}/../current-fake-layer 5\n"
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
        self.assertIn("bitbake-layers remove-layer", sync_cmd)
        self.assertIn("|| true", sync_cmd)
        self.assertIn("../current-fake-layer", sync_cmd)
        self.assertIn("bitbake-layers add-layer", sync_cmd)
        for layer in layers:
            self.assertIn(layer, sync_cmd)
        self.assertIn(f"touch {stamp_path}", sync_cmd)

    def test_stamp_exists_match_nothing_to_do(self):
        """
        Stamp exists, and current layers (after normalization) match the desired 'argv'.
        Expected:
          - '_run_bash' is called with 'bitbake-layers show-layers'
          - sync_layers() is NOT triggered
          - subprocess.run must NOT be called
        """
        # create variables needed for the test
        yocto_dir = "/abs/path/to/yocto"
        work_dir = "build-dom0"
        layers = ["../fake-layer1", "../fake-layer2"]
        stamp_path = "/tmp/layers.stamp"

        # show-layers returns exactly these layers, so they match desired argv
        show_layers_stdout = (
            "layer  path                     priority\n"
            "========================================\n"
            "meta   /abs/poky/meta           7\n"
            "meta   /abs/poky/meta-poky      5\n"
            "meta   /abs/poky/meta-yocto-bsp 5\n"
            f"meta   {yocto_dir}/{work_dir}/{layers[0]} 5\n"
            f"meta   {yocto_dir}/{work_dir}/{layers[1]} 5\n"
        )

        with patch("moulin.builders.yocto.Path.exists", return_value=True), \
             patch("moulin.builders.yocto._run_bash") as mock_run, \
             patch("moulin.builders.yocto.subprocess.run") as mock_subproc:

            # _run_bash simulates returning show-layers output
            mock_run.return_value = Mock(returncode=0, stdout=show_layers_stdout, stderr="")

            yocto_mod.handle_utility_call(
                conf=None,
                argv=[
                    "--yocto-dir", yocto_dir,
                    "--work-dir", work_dir,
                    "--layers", *layers,
                    "--stamp", stamp_path,
                ],
            )

        # verify that show-layers was called
        self.assertIsNotNone(mock_run.call_args)
        self.assertIn("bitbake-layers show-layers", mock_run.call_args[0][0])

        # subprocess.run must NOT be called when layers match
        mock_subproc.assert_not_called()
