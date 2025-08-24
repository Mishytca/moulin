import unittest
import shlex
from unittest.mock import patch, Mock
import moulin.builders.yocto as yocto_mod
from pathlib import Path


class TestYoctoUtilitySyncLayers(unittest.TestCase):
    def test_first_run_no_stamp_calls_add_layer(self):
        """
        First run (stamp file does not exist):
        - correct list of layers is passed to "bitbake-layers add-layer"
        - stamp file is updated via "touch"
        """
        # create variables needed for the test
        yocto_dir = "/abs/path/to/yocto"
        work_dir = "build-dom0"
        layers = ["../fake-layer1", "../fake-layer2"]
        stamp_path = "/tmp/layers.stamp"

        # stamp file does not exist -> return_value=False
        with patch("moulin.builders.yocto.Path.exists", return_value=False), \
             patch("moulin.builders.yocto._run_bash") as mock_run:

            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            yocto_mod.handle_utility_call(
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

        # cmd contains bitbake-layers add-layer and all layers
        self.assertIn("bitbake-layers add-layer", cmd)
        for layer in layers:
            self.assertIn(shlex.quote(layer), cmd)
        self.assertIn(f"touch {shlex.quote(stamp_path)}", cmd)

    def test_stamp_exists_adds_and_removes_layers(self):
        """
        Stamp exists and layer set differs:
        - obsolete layer is removed
        - missing layers are added
        - stamp is updated
        """
        # create variables needed for the test
        yocto_dir = "/abs/path/to/yocto"
        work_dir = "build-dom0"
        layers = ["../fake-layer1", "../fake-layer2"]
        stamp_path = "/tmp/layers.stamp"

        # -> this one is *not* in layers and must be removed
        unneeded_rel = "../current-fake-layer"

        # absolute forms (code may add/remove by ABS)
        build_abs = (Path(yocto_dir) / work_dir).resolve(strict=False)
        layers_abs = [str((build_abs / r).resolve(strict=False)) for r in layers]
        unneeded_abs = str((build_abs / unneeded_rel).resolve(strict=False))

        # Realistic show-layers output: 3 Yocto core layers + one unneeded managed layer
        show_layers_stdout = (
            "layer   path                    priority\n"
            "========================================\n"
            f"meta   {yocto_dir}/poky/meta           7\n"
            f"meta   {yocto_dir}/poky/meta-poky      5\n"
            f"meta   {yocto_dir}/poky/meta-yocto-bsp 5\n"
            f"meta   {unneeded_abs} 5\n"
        )

        # stamp exists -> return_value=True
        with patch("moulin.builders.yocto.Path.exists", return_value=True), \
             patch("moulin.builders.yocto._run_bash") as mock_run:

            # 1st call -> show-layers, 2nd -> remove obsolete and add missing layers
            mock_run.side_effect = [
                Mock(returncode=0, stdout=show_layers_stdout, stderr=""),
                Mock(returncode=0, stdout="", stderr=""),
            ]

            yocto_mod.handle_utility_call(
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

        # check remove-layer segment
        self.assertIn("bitbake-layers remove-layer", cmd)
        rm_seg = cmd.split("bitbake-layers remove-layer", 1)[1].split(" && ", 1)[0]
        # unneeded_abs must be present in remove
        self.assertIn(shlex.quote(unneeded_abs), rm_seg, msg=f"{unneeded_abs} \
            not found in remove-layer segment:\n{rm_seg}")

        # check add-layer segment
        self.assertIn("bitbake-layers add-layer", cmd)
        add_seg = cmd.split("bitbake-layers add-layer", 1)[1].split(" && ", 1)[0]

        # all layers_abs must be in add-layer
        for p in layers_abs:
            self.assertIn(shlex.quote(p), add_seg, msg=f"{p} \
            not found in add-layer segment:\n{add_seg}")
        # there shouldn't be unneeded_abs there
        self.assertNotIn(shlex.quote(unneeded_abs), add_seg, msg=f"{unneeded_abs} \
            must NOT be in add-layer segment:\n{add_seg}")

        # stamp file was updated
        self.assertIn(f"touch {shlex.quote(stamp_path)}", cmd)

    def test_stamp_exists_only_core_layers_adds_yaml_layers(self):
        """
        Stamp exists, but only Yocto core layers are present:
        - no layers are removed
        - YAML layers are added
        - stamp is updated
        """
        # create variables needed for the test
        yocto_dir = "/abs/path/to/yocto"
        work_dir = "build-dom0"
        layers = ["../fake-layer1", "../fake-layer2"]
        stamp_path = "/tmp/layers.stamp"

        # absolute forms (code may add/remove by ABS)
        build_abs = (Path(yocto_dir) / work_dir).resolve(strict=False)
        layers_abs = [str((build_abs / r).resolve(strict=False)) for r in layers]

        # Realistic show-layers output: only 3 Yocto core layers
        show_layers_stdout = (
            "layer   path                    priority\n"
            "========================================\n"
            f"meta   {yocto_dir}/poky/meta           7\n"
            f"meta   {yocto_dir}/poky/meta-poky      5\n"
            f"meta   {yocto_dir}/poky/meta-yocto-bsp 5\n"
        )

        # stamp exists -> return_value=True
        with patch("moulin.builders.yocto.Path.exists", return_value=True), \
             patch("moulin.builders.yocto._run_bash") as mock_run:

            # 1st call -> show-layers, 2nd -> apply diff
            mock_run.side_effect = [
                Mock(returncode=0, stdout=show_layers_stdout, stderr=""),
                Mock(returncode=0, stdout="", stderr=""),
            ]

            yocto_mod.handle_utility_call(
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

        # no remove-layer command is needed
        self.assertNotIn("bitbake-layers remove-layer", cmd)

        # check add-layer segment
        self.assertIn("bitbake-layers add-layer", cmd)
        add_seg = cmd.split("bitbake-layers add-layer", 1)[1].split(" && ", 1)[0]

        # all layers_abs must be in add-layer
        for p in layers_abs:
            self.assertIn(
                shlex.quote(p),
                add_seg,
                msg=f"{p} not found in add-layer segment:\n{add_seg}",
            )

        # stamp file was updated
        self.assertIn(f"touch {shlex.quote(stamp_path)}", cmd)

    def test_stamp_exists_identical_layers_no_add_or_remove(self):
        """
        Stamp exists and layers already match YAML:
        - no layers are removed
        - no layers are added
        - stamp is updated
        """
        # create variables needed for the test
        yocto_dir = "/abs/path/to/yocto"
        work_dir = "build-dom0"
        layers = ["../fake-layer1", "../fake-layer2"]
        stamp_path = "/tmp/layers.stamp"

        # absolute forms (code may add/remove by ABS)
        build_abs = (Path(yocto_dir) / work_dir).resolve(strict=False)
        layers_abs = [str((build_abs / r).resolve(strict=False)) for r in layers]

        # Realistic show-layers output: core layers + managed layers in YAML order
        show_layers_stdout = (
            "layer   path                    priority\n"
            "========================================\n"
            f"meta   {yocto_dir}/poky/meta           7\n"
            f"meta   {yocto_dir}/poky/meta-poky      5\n"
            f"meta   {yocto_dir}/poky/meta-yocto-bsp 5\n"
            f"fake1  {layers_abs[0]} 5\n"
            f"fake2  {layers_abs[1]} 5\n"
        )

        # stamp exists -> return_value=True
        with patch("moulin.builders.yocto.Path.exists", return_value=True), \
             patch("moulin.builders.yocto._run_bash") as mock_run:

            # 1st call -> show-layers, 2nd -> only touch stamp
            mock_run.side_effect = [
                Mock(returncode=0, stdout=show_layers_stdout, stderr=""),
                Mock(returncode=0, stdout="", stderr=""),
            ]

            yocto_mod.handle_utility_call(
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

        # no add/remove commands are needed
        self.assertNotIn("bitbake-layers remove-layer", cmd)
        self.assertNotIn("bitbake-layers add-layer", cmd)

        # stamp file was updated
        self.assertIn(f"touch {shlex.quote(stamp_path)}", cmd)

    def test_stamp_exists_reorders_layers_to_match_yaml_order(self):
        """
        Stamp exists and layers are the same, but order differs:
        - managed layers are removed in the current order
        - managed layers are added back in YAML order
        - stamp is updated
        """
        # create variables needed for the test
        yocto_dir = "/abs/path/to/yocto"
        work_dir = "build-dom0"
        layers = ["../fake-layer1", "../fake-layer2"]
        stamp_path = "/tmp/layers.stamp"

        # absolute forms (code may add/remove by ABS)
        build_abs = (Path(yocto_dir) / work_dir).resolve(strict=False)
        layers_abs = [str((build_abs / r).resolve(strict=False)) for r in layers]

        # Realistic show-layers output: managed layers are in reverse order
        show_layers_stdout = (
            "layer   path                    priority\n"
            "========================================\n"
            f"meta   {yocto_dir}/poky/meta           7\n"
            f"meta   {yocto_dir}/poky/meta-poky      5\n"
            f"meta   {yocto_dir}/poky/meta-yocto-bsp 5\n"
            f"fake2  {layers_abs[1]} 5\n"
            f"fake1  {layers_abs[0]} 5\n"
        )

        # stamp exists -> return_value=True
        with patch("moulin.builders.yocto.Path.exists", return_value=True), \
             patch("moulin.builders.yocto._run_bash") as mock_run:

            # 1st call -> show-layers, 2nd -> reorder layers
            mock_run.side_effect = [
                Mock(returncode=0, stdout=show_layers_stdout, stderr=""),
                Mock(returncode=0, stdout="", stderr=""),
            ]

            yocto_mod.handle_utility_call(
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

        # check remove-layer segment
        self.assertIn("bitbake-layers remove-layer", cmd)
        rm_seg = cmd.split("bitbake-layers remove-layer", 1)[1].split(" && ", 1)[0]

        # check add-layer segment
        self.assertIn("bitbake-layers add-layer", cmd)
        add_seg = cmd.split("bitbake-layers add-layer", 1)[1].split(" && ", 1)[0]

        # remove order must follow the current show-layers order
        self.assertLess(
            rm_seg.index(shlex.quote(layers_abs[1])),
            rm_seg.index(shlex.quote(layers_abs[0])),
        )

        # add order must follow the YAML order
        self.assertLess(
            add_seg.index(shlex.quote(layers_abs[0])),
            add_seg.index(shlex.quote(layers_abs[1])),
        )

        # stamp file was updated
        self.assertIn(f"touch {shlex.quote(stamp_path)}", cmd)

    def test_stamp_exists_only_removes_obsolete_layer(self):
        """
        Stamp exists and YAML has fewer layers:
        - obsolete layer is removed
        - no layers are added
        - stamp is updated
        """
        # create variables needed for the test
        yocto_dir = "/abs/path/to/yocto"
        work_dir = "build-dom0"
        layers = ["../fake-layer1"]
        stamp_path = "/tmp/layers.stamp"

        # absolute forms (code may add/remove by ABS)
        build_abs = (Path(yocto_dir) / work_dir).resolve(strict=False)
        layers_abs = [str((build_abs / r).resolve(strict=False)) for r in layers]
        obsolete_abs = str((build_abs / "../obsolete-layer").resolve(strict=False))

        # Realistic show-layers output: core layers + one obsolete managed layer
        show_layers_stdout = (
            "layer   path                    priority\n"
            "========================================\n"
            f"meta   {yocto_dir}/poky/meta           7\n"
            f"meta   {yocto_dir}/poky/meta-poky      5\n"
            f"meta   {yocto_dir}/poky/meta-yocto-bsp 5\n"
            f"fake1  {layers_abs[0]} 5\n"
            f"obsolete  {obsolete_abs} 5\n"
        )

        # stamp exists -> return_value=True
        with patch("moulin.builders.yocto.Path.exists", return_value=True), \
             patch("moulin.builders.yocto._run_bash") as mock_run:

            # 1st call -> show-layers, 2nd -> remove obsolete layer
            mock_run.side_effect = [
                Mock(returncode=0, stdout=show_layers_stdout, stderr=""),
                Mock(returncode=0, stdout="", stderr=""),
            ]

            yocto_mod.handle_utility_call(
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

        # check remove-layer segment
        self.assertIn("bitbake-layers remove-layer", cmd)
        rm_seg = cmd.split("bitbake-layers remove-layer", 1)[1].split(" && ", 1)[0]

        # obsolete layer must be removed
        self.assertIn(shlex.quote(obsolete_abs), rm_seg)

        # no add-layer command is needed
        self.assertNotIn("bitbake-layers add-layer", cmd)

        # stamp file was updated
        self.assertIn(f"touch {shlex.quote(stamp_path)}", cmd)

    def test_stamp_exists_only_adds_missing_layer(self):
        """
        Stamp exists and YAML has more layers:
        - no layers are removed
        - missing layer is added
        - stamp is updated
        """
        # create variables needed for the test
        yocto_dir = "/abs/path/to/yocto"
        work_dir = "build-dom0"
        layers = ["../fake-layer1", "../fake-layer2"]
        stamp_path = "/tmp/layers.stamp"

        # absolute forms (code may add/remove by ABS)
        build_abs = (Path(yocto_dir) / work_dir).resolve(strict=False)
        layers_abs = [str((build_abs / r).resolve(strict=False)) for r in layers]

        # Realistic show-layers output: core layers + only first YAML layer
        show_layers_stdout = (
            "layer   path                    priority\n"
            "========================================\n"
            f"meta   {yocto_dir}/poky/meta           7\n"
            f"meta   {yocto_dir}/poky/meta-poky      5\n"
            f"meta   {yocto_dir}/poky/meta-yocto-bsp 5\n"
            f"fake1  {layers_abs[0]} 5\n"
        )

        # stamp exists -> return_value=True
        with patch("moulin.builders.yocto.Path.exists", return_value=True), \
             patch("moulin.builders.yocto._run_bash") as mock_run:

            # 1st call -> show-layers, 2nd -> add missing layer
            mock_run.side_effect = [
                Mock(returncode=0, stdout=show_layers_stdout, stderr=""),
                Mock(returncode=0, stdout="", stderr=""),
            ]

            yocto_mod.handle_utility_call(
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

        # no remove-layer command is needed
        self.assertNotIn("bitbake-layers remove-layer", cmd)

        # check add-layer segment
        self.assertIn("bitbake-layers add-layer", cmd)
        add_seg = cmd.split("bitbake-layers add-layer", 1)[1].split(" && ", 1)[0]

        # missing layer must be added
        self.assertIn(shlex.quote(layers_abs[1]), add_seg)

        # stamp file was updated
        self.assertIn(f"touch {shlex.quote(stamp_path)}", cmd)

    def test_layers_with_spaces_are_quoted(self):
        """
        Stamp exists and YAML layer path contains spaces:
        - no layers are removed
        - missing layer with spaces is added
        - layer path and stamp path are shell-quoted
        """
        # create variables needed for the test
        yocto_dir = "/abs/path/to/yocto"
        work_dir = "build-dom0"
        layers = ["../fake layer with spaces"]
        stamp_path = "/tmp/layers stamp"

        # absolute forms (code may add/remove by ABS)
        build_abs = (Path(yocto_dir) / work_dir).resolve(strict=False)
        layers_abs = [str((build_abs / r).resolve(strict=False)) for r in layers]

        # Realistic show-layers output: only 3 Yocto core layers
        show_layers_stdout = (
            "layer   path                    priority\n"
            "========================================\n"
            f"meta   {yocto_dir}/poky/meta           7\n"
            f"meta   {yocto_dir}/poky/meta-poky      5\n"
            f"meta   {yocto_dir}/poky/meta-yocto-bsp 5\n"
        )

        # stamp exists -> return_value=True
        with patch("moulin.builders.yocto.Path.exists", return_value=True), \
             patch("moulin.builders.yocto._run_bash") as mock_run:

            # 1st call -> show-layers, 2nd -> add quoted layer
            mock_run.side_effect = [
                Mock(returncode=0, stdout=show_layers_stdout, stderr=""),
                Mock(returncode=0, stdout="", stderr=""),
            ]

            yocto_mod.handle_utility_call(
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

        # no remove-layer command is needed
        self.assertNotIn("bitbake-layers remove-layer", cmd)

        # check add-layer segment
        self.assertIn("bitbake-layers add-layer", cmd)
        add_seg = cmd.split("bitbake-layers add-layer", 1)[1].split(" && ", 1)[0]

        # layer path with spaces must be shell-quoted
        self.assertIn(shlex.quote(layers_abs[0]), add_seg)

        # stamp path with spaces must be shell-quoted
        self.assertIn(f"touch {shlex.quote(stamp_path)}", cmd)

    def test_stamp_exists_differs_and_reorders_layers(self):
        """
        Stamp exists and simple add/remove would not preserve YAML order:
        - obsolete layer is removed
        - existing managed layer is removed because full recreate is needed
        - YAML layers are added back in YAML order
        - stamp is updated
        """
        # create variables needed for the test
        yocto_dir = "/abs/path/to/yocto"
        work_dir = "build-dom0"
        layers = ["../fake-layer1", "../fake-layer2"]
        stamp_path = "/tmp/layers.stamp"

        # absolute forms (code may add/remove by ABS)
        build_abs = (Path(yocto_dir) / work_dir).resolve(strict=False)
        layers_abs = [str((build_abs / r).resolve(strict=False)) for r in layers]
        obsolete_abs = str((build_abs / "../obsolete-layer").resolve(strict=False))

        # Realistic show-layers output: one managed layer is present and one obsolete layer exists
        show_layers_stdout = (
            "layer   path                    priority\n"
            "========================================\n"
            f"meta   {yocto_dir}/poky/meta           7\n"
            f"meta   {yocto_dir}/poky/meta-poky      5\n"
            f"meta   {yocto_dir}/poky/meta-yocto-bsp 5\n"
            f"fake2  {layers_abs[1]} 5\n"
            f"obsolete  {obsolete_abs} 5\n"
        )

        # stamp exists -> return_value=True
        with patch("moulin.builders.yocto.Path.exists", return_value=True), \
             patch("moulin.builders.yocto._run_bash") as mock_run:

            # 1st call -> show-layers, 2nd -> recreate managed layers in YAML order
            mock_run.side_effect = [
                Mock(returncode=0, stdout=show_layers_stdout, stderr=""),
                Mock(returncode=0, stdout="", stderr=""),
            ]

            yocto_mod.handle_utility_call(
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

        # check remove-layer segment
        self.assertIn("bitbake-layers remove-layer", cmd)
        rm_seg = cmd.split("bitbake-layers remove-layer", 1)[1].split(" && ", 1)[0]

        # obsolete layer and existing managed layer must be removed
        self.assertIn(shlex.quote(obsolete_abs), rm_seg)
        self.assertIn(shlex.quote(layers_abs[1]), rm_seg)

        # check add-layer segment
        self.assertIn("bitbake-layers add-layer", cmd)
        add_seg = cmd.split("bitbake-layers add-layer", 1)[1].split(" && ", 1)[0]

        # YAML layers must be added back
        self.assertIn(shlex.quote(layers_abs[0]), add_seg)
        self.assertIn(shlex.quote(layers_abs[1]), add_seg)

        # YAML layers must be added back in YAML order
        self.assertLess(
            add_seg.index(shlex.quote(layers_abs[0])),
            add_seg.index(shlex.quote(layers_abs[1])),
        )

        # stamp file was updated
        self.assertIn(f"touch {shlex.quote(stamp_path)}", cmd)
