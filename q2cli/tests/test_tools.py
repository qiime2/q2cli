# ----------------------------------------------------------------------------
# Copyright (c) 2016-2018, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import os
import shutil
import unittest
import tempfile

from click.testing import CliRunner
from qiime2 import Artifact
from qiime2.core.testing.util import get_dummy_plugin

from q2cli.tools import tools
from q2cli.commands import RootCommand


class TestInspectMetadata(unittest.TestCase):
    def setUp(self):
        dummy_plugin = get_dummy_plugin()

        self.runner = CliRunner()
        self.tempdir = tempfile.mkdtemp(prefix='qiime2-q2cli-test-temp-')

        self.metadata_file_mixed_types = os.path.join(
                self.tempdir, 'metadata-mixed-types.tsv')
        with open(self.metadata_file_mixed_types, 'w') as f:
            f.write('id\tnumbers\tstrings\n0\t42\tabc\n1\t-1.5\tdef\n')

        self.bad_metadata_file = os.path.join(
                self.tempdir, 'bad-metadata.tsv')
        with open(self.bad_metadata_file, 'w') as f:
            f.write('wrong\tnumbers\tstrings\nid1\t42\tabc\nid2\t-1.5\tdef\n')

        self.metadata_artifact = os.path.join(self.tempdir, 'metadata.qza')
        Artifact.import_data(
            'Mapping', {'a': 'dog', 'b': 'cat'}).save(self.metadata_artifact)

        self.ints1 = os.path.join(self.tempdir, 'ints1.qza')
        ints1 = Artifact.import_data(
            'IntSequence1', [0, 42, 43], list)
        ints1.save(self.ints1)

        self.viz = os.path.join(self.tempdir, 'viz.qzv')
        most_common_viz = dummy_plugin.actions['most_common_viz']
        self.viz = most_common_viz(ints1).visualization.save(self.viz)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_artifact_w_metadata(self):
        result = self.runner.invoke(
            tools, ['inspect-metadata', self.metadata_artifact])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('COLUMN NAME  TYPE', result.output)
        self.assertIn("===========  ===========", result.output)
        self.assertIn("a  categorical", result.output)
        self.assertIn("b  categorical", result.output)
        self.assertIn("IDS:  1", result.output)
        self.assertIn("COLUMNS:  2", result.output)

    def test_artifact_no_metadata(self):
        result = self.runner.invoke(tools, ['inspect-metadata', self.ints1])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("IntSequence1 cannot be viewed as QIIME 2 metadata",
                      result.output)

    def test_visualization(self):
        # make a viz first:
        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')
        # build output parameter arguments and expected output file names
        viz_path = os.path.join(self.tempdir, 'viz.qzv')
        result = self.runner.invoke(
            command, ['most-common-viz', '--i-ints', self.ints1,
                      '--o-visualization', viz_path, '--verbose'])

        result = self.runner.invoke(tools, ['inspect-metadata', viz_path])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Visualizations cannot be viewed as QIIME 2 metadata",
                      result.output)

    def test_metadata_file(self):
        result = self.runner.invoke(
            tools, ['inspect-metadata', self.metadata_file_mixed_types])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('COLUMN NAME  TYPE', result.output)
        self.assertIn("===========  ===========", result.output)
        self.assertIn("numbers  numeric", result.output)
        self.assertIn("strings  categorical", result.output)
        self.assertIn("IDS:  2", result.output)
        self.assertIn("COLUMNS:  2", result.output)

    def test_bad_metadata_file(self):
        result = self.runner.invoke(
            tools, ['inspect-metadata', self.bad_metadata_file])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("'wrong'", result.output)

    def test_tsv(self):
        result = self.runner.invoke(tools, [
            'inspect-metadata', self.metadata_file_mixed_types, '--tsv'])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('COLUMN NAME\tTYPE', result.output)
        self.assertIn("numbers\tnumeric", result.output)
        self.assertIn("strings\tcategorical", result.output)

        self.assertNotIn("=", result.output)
        self.assertNotIn("IDS:", result.output)
        self.assertNotIn("COLUMNS:", result.output)

    def test_merged_metadata(self):
        result = self.runner.invoke(tools, [
            'inspect-metadata',
            self.metadata_artifact,
            self.metadata_file_mixed_types])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('COLUMN NAME  TYPE', result.output)
        self.assertIn("===========  ===========", result.output)
        self.assertIn("a  categorical", result.output)
        self.assertIn("b  categorical", result.output)
        self.assertIn("numbers  numeric", result.output)
        self.assertIn("strings  categorical", result.output)
        self.assertIn("IDS:  1", result.output)  # only 1 ID is shared
        self.assertIn("COLUMNS:  4", result.output)

    def test_export_to_dir_w_format(self):
        output_path = os.path.join(self.tempdir, 'output')
        result = self.runner.invoke(tools, [
            'export', '--input-path', self.ints1, '--output-path', output_path,
            '--output-format', 'IntSequenceDirectoryFormat'
        ])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(os.path.isdir(output_path))

    def test_export_to_dir_no_format(self):
        output_path = os.path.join(self.tempdir, 'output')
        self.runner.invoke(tools, [
            'export', '--input-path', self.viz, '--output-path', output_path
        ])

        self.assertTrue(os.path.isdir(output_path))
        self.assertIn('index.html', os.listdir(output_path))
        self.assertIn('index.tsv', os.listdir(output_path))

    def test_export_to_file(self):
        output_path = os.path.join(self.tempdir, 'output')
        result = self.runner.invoke(tools, [
            'export', '--input-path', self.ints1, '--output-path', output_path,
            '--output-format', 'IntSequenceFormatV2'
            ])

        with open(output_path, 'r') as f:
            file = f.read()
        self.assertEqual(result.exit_code, 0)
        self.assertIn('0', file)
        self.assertIn('42', file)
        self.assertIn('43', file)

    def test_export_visualization_to_dir(self):
        output_path = os.path.join(self.tempdir, 'output')
        self.runner.invoke(tools, [
            'export', '--input-path', self.viz, '--output-path', output_path
        ])

        self.assertIn('index.html', os.listdir(output_path))
        self.assertIn('index.tsv', os.listdir(output_path))
        self.assertTrue(os.path.isdir(output_path))

    def test_export_visualization_w_format(self):
        output_path = os.path.join(self.tempdir, 'output')
        result = self.runner.invoke(tools, [
            'export', '--input-path', self.viz, '--output-path', output_path,
            '--output-format', 'IntSequenceDirectoryFormat'
        ])

        self.assertEqual(result.exit_code, 1)
        self.assertIn('visualization', result.output)
        self.assertIn('--output-format', result.output)

    def test_export_path_file_is_replaced(self):
        output_path = os.path.join(self.tempdir, 'output')
        with open(output_path, 'w') as file:
            file.write('HelloWorld')
        self.runner.invoke(tools, [
            'export', '--input-path', self.ints1, '--output-path', output_path,
            '--output-format', 'IntSequenceFormatV2'
        ])
        with open(output_path, 'r') as f:
            file = f.read()
        self.assertNotIn('HelloWorld', file)

    def test_export_to_file_success_message(self):
        self.assertTrue(False)


if __name__ == "__main__":
    unittest.main()
