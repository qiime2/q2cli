# ----------------------------------------------------------------------------
# Copyright (c) 2016--, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------

import os.path
import unittest
import tempfile

from click.testing import CliRunner
from qiime import Artifact
from qiime.core.testing.type import IntSequence1

from q2cli._info import info
from q2cli._tools import tools
from q2cli.cli import QiimeCLI


class CliTests(unittest.TestCase):

    def setUp(self):
        self.qiime_cli = QiimeCLI()
        self.runner = CliRunner()
        self.artifact1 = Artifact._from_view([0, 42, 43], IntSequence1, None)

    def test_info(self):
        result = self.runner.invoke(info)
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.output.startswith('System versions\nPython'))
        self.assertTrue('Installed plugins\ndummy-plugin' in result.output)

    def test_tools(self):
        result = self.runner.invoke(tools)
        self.assertEqual(result.exit_code, 0)

    def test_extract(self):
        with tempfile.TemporaryDirectory() as output_dir:
            with tempfile.NamedTemporaryFile() as f:
                self.artifact1.save(f.name)
                result = self.runner.invoke(
                    tools, ['extract', f.name, '--output-dir', output_dir])
                self.assertEqual(result.exit_code, 0)
                data_f = open(os.path.join(output_dir,
                                           os.path.split(f.name)[1],
                                           'data', 'ints.txt'))
                self.assertEqual(data_f.read(), "0\n42\n43\n")

    def test_split_ints_output_extensions_not_specified(self):
        command = self.qiime_cli.get_command(ctx=None, name='dummy-plugin')
        with tempfile.TemporaryDirectory() as output_dir:
            left_path = os.path.join(output_dir, 'left')
            expected_left_path = os.path.join(output_dir, 'left.qza')
            right_path = os.path.join(output_dir, 'right')
            expected_right_path = os.path.join(output_dir, 'right.qza')
            with tempfile.NamedTemporaryFile() as f:
                self.artifact1.save(f.name)
                import subprocess
                cp = subprocess.run(['qiime', 'dummy-plugin', 'split_ints', '--ints', f.name, '--left', left_path, '--right', right_path])
                print(cp.stdout)
                print(cp.stderr)
                result = self.runner.invoke(
                    command, ['split_ints', '--ints', f.name,
                              '--left', left_path, '--right', right_path])
                self.assertTrue(os.path.exists(expected_left_path))
                self.assertTrue(os.path.exists(expected_right_path))
                left = Artifact.load(expected_left_path)
                right = Artifact.load(expected_right_path)
                self.assertEqual(left.view(list), [0])
                self.assertEqual(right.view(list), [42, 43])
                self.assertEqual(result.exit_code, 0)

    def test_split_ints_output_extensions_specified(self):
        command = self.qiime_cli.get_command(ctx=None, name='dummy-plugin')
        with tempfile.TemporaryDirectory() as output_dir:
            left_path = os.path.join(output_dir, 'left.qza')
            right_path = os.path.join(output_dir, 'right.qza')
            with tempfile.NamedTemporaryFile() as f:
                self.artifact1.save(f.name)

                result = self.runner.invoke(
                    command, ['split_ints', '--ints', f.name,
                              '--left', left_path, '--right', right_path])
                self.assertTrue(os.path.exists(left_path))
                self.assertTrue(os.path.exists(right_path))
                left = Artifact.load(left_path)
                right = Artifact.load(right_path)
                self.assertEqual(left.view(list), [0])
                self.assertEqual(right.view(list), [42, 43])
                self.assertEqual(result.exit_code, 0)
