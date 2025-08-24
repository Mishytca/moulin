import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import moulin.builders.yocto as yocto_mod


class TestYoctoUtilitySyncLayers(unittest.TestCase):
    def setUp(self):
        self.yocto_dir = "/abs/path/to/yocto"
        self.work_dir = "build-dom0"
        self.stamp_path = "/tmp/layers.stamp"
        self.build_abs = (Path(self.yocto_dir) / self.work_dir).resolve(strict=False)

    def _argv(self, layers):
        return [
            "--yocto-dir", self.yocto_dir,
            "--distro-dir", "poky",
            "--work-dir", self.work_dir,
            "--layers", *layers,
            "--stamp", self.stamp_path,
        ]

    def _abs(self, layer):
        return str((self.build_abs / layer).resolve(strict=False))

    def _show_layers(self, extra_layers):
        rows = [
            f"meta                  {self.yocto_dir}/poky/meta           7",
            f"meta-poky             {self.yocto_dir}/poky/meta-poky      5",
            f"meta-yocto-bsp        {self.yocto_dir}/poky/meta-yocto-bsp 5",
        ]
        rows.extend(f"meta-custom           {layer} 8" for layer in extra_layers)
        return (
            "layer                 path                    priority\n"
            "========================================\n"
            + "\n".join(rows)
            + "\n"
        )

    def _run_utility(self, *, stamp_exists, layers, current_layers=None):
        with patch("moulin.builders.yocto.Path.exists", return_value=stamp_exists), \
             patch("moulin.builders.yocto._run_bash") as run_bash:
            if stamp_exists:
                run_bash.side_effect = [
                    Mock(returncode=0, stdout=self._show_layers(current_layers or []), stderr=""),
                    Mock(returncode=0, stdout="", stderr=""),
                ]
            else:
                run_bash.return_value = Mock(returncode=0, stdout="", stderr="")

            yocto_mod.handle_utility_call(argv=self._argv(layers))
            return run_bash

    def test_first_run_no_stamp_adds_configured_layers_and_touches_stamp(self):
        layers = ["../fake-layer1", "../fake-layer2"]

        run_bash = self._run_utility(stamp_exists=False, layers=layers)

        run_bash.assert_called_once()
        cmd = run_bash.call_args[0][0]
        self.assertIn("bitbake-layers add-layer", cmd)
        self.assertNotIn("bitbake-layers remove-layer", cmd)
        for layer in layers:
            self.assertIn(layer, cmd)
        self.assertIn(f"touch {self.stamp_path}", cmd)

    def test_stamp_exists_conf_missing_adds_all_configured_layers(self):
        layers = ["../fake-layer1", "../fake-layer2"]
        layers_abs = [self._abs(layer) for layer in layers]

        run_bash = self._run_utility(stamp_exists=True, layers=layers, current_layers=[])

        self.assertEqual(run_bash.call_count, 2)
        cmd = run_bash.call_args[0][0]
        self.assertNotIn("bitbake-layers remove-layer", cmd)
        self.assertIn("bitbake-layers add-layer", cmd)
        add_seg = cmd.split("bitbake-layers add-layer", 1)[1].split(" && ", 1)[0]
        self.assertLess(add_seg.index(layers_abs[0]), add_seg.index(layers_abs[1]))
        for layer in layers_abs:
            self.assertIn(layer, add_seg)
        self.assertIn(f"touch {self.stamp_path}", cmd)

    def test_stamp_exists_syncs_added_and_removed_layers(self):
        layers = ["../fake-layer1", "../fake-layer2"]
        layers_abs = [self._abs(layer) for layer in layers]
        unneeded_abs = self._abs("../current-fake-layer")

        run_bash = self._run_utility(
            stamp_exists=True,
            layers=layers,
            current_layers=[unneeded_abs],
        )

        self.assertEqual(run_bash.call_count, 2)
        cmd = run_bash.call_args[0][0]
        rm_seg = cmd.split("bitbake-layers remove-layer", 1)[1].split(" && ", 1)[0]
        self.assertIn(unneeded_abs, rm_seg)
        add_seg = cmd.split("bitbake-layers add-layer", 1)[1].split(" && ", 1)[0]
        self.assertLess(add_seg.index(layers_abs[0]), add_seg.index(layers_abs[1]))
        for layer in layers_abs:
            self.assertIn(layer, add_seg)
        self.assertNotIn(unneeded_abs, add_seg)
        self.assertIn(f"touch {self.stamp_path}", cmd)

    def test_stamp_exists_identical_layers_does_not_apply_changes(self):
        layers = ["../fake-layer1", "../fake-layer2"]
        layers_abs = [self._abs(layer) for layer in layers]

        run_bash = self._run_utility(
            stamp_exists=True,
            layers=layers,
            current_layers=layers_abs,
        )

        run_bash.assert_called_once()
        self.assertIn("bitbake-layers show-layers", run_bash.call_args[0][0])

    def test_show_layers_order_does_not_affect_comparison(self):
        layers = ["../fake-layer1", "../fake-layer2"]
        layers_abs = [self._abs(layer) for layer in layers]

        run_bash = self._run_utility(
            stamp_exists=True,
            layers=layers,
            current_layers=list(reversed(layers_abs)),
        )

        run_bash.assert_called_once()
        self.assertIn("bitbake-layers show-layers", run_bash.call_args[0][0])

    def test_shell_arguments_are_quoted(self):
        layers = ["../layer with space", "../plain-layer"]
        stamp_path = "/tmp/layers stamp;rm -rf x"

        with patch("moulin.builders.yocto.Path.exists", return_value=False), \
             patch("moulin.builders.yocto._run_bash") as run_bash:
            yocto_mod.handle_utility_call(argv=[
                "--yocto-dir", "/abs/path/to/yocto root",
                "--distro-dir", "openembedded core",
                "--work-dir", "build dir",
                "--layers", *layers,
                "--stamp", stamp_path,
            ])

        cmd = run_bash.call_args[0][0]
        self.assertIn("cd '/abs/path/to/yocto root'", cmd)
        self.assertIn("'openembedded core/oe-init-build-env'", cmd)
        self.assertIn("'build dir'", cmd)
        self.assertIn("'../layer with space'", cmd)
        self.assertIn("'/tmp/layers stamp;rm -rf x'", cmd)


if __name__ == "__main__":
    unittest.main()
