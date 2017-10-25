# ----------------------------------------------------------------------------
# Copyright (c) 2016-2017, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import os.path
import unittest
import tempfile
import shutil

from click.testing import CliRunner
from qiime2 import Artifact, Visualization
from qiime2.core.testing.type import IntSequence1, IntSequence2
from qiime2.core.testing.util import get_dummy_plugin
from qiime2.core.archive import ImportProvenanceCapture

from q2cli.info import info
from q2cli.tools import tools
from q2cli.commands import RootCommand


class CliTests(unittest.TestCase):
    def setUp(self):
        get_dummy_plugin()
        self.runner = CliRunner()
        self.tempdir = tempfile.mkdtemp(prefix='qiime2-q2cli-test-temp-')
        self.artifact1_path = os.path.join(self.tempdir, 'a1.qza')
        self.mapping_path = os.path.join(self.tempdir, 'mapping.qza')

        artifact1 = Artifact.import_data(IntSequence1, [0, 42, 43])
        artifact1.save(self.artifact1_path)
        self.artifact1_root_dir = str(artifact1.uuid)

        mapping = Artifact.import_data('Mapping', {'foo': '42'})
        mapping.save(self.mapping_path)


    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_info(self):
        result = self.runner.invoke(info)
        self.assertEqual(result.exit_code, 0)
        # May not always start with "System versions" if cache updating message
        # is printed.
        self.assertIn('System versions', result.output)
        self.assertIn('Installed plugins', result.output)
        self.assertIn('dummy-plugin', result.output)

    def test_list_commands(self):
        # top level commands, including a plugin, are present
        qiime_cli = RootCommand()
        commands = qiime_cli.list_commands(ctx=None)
        self.assertTrue('info' in commands)
        self.assertTrue('tools' in commands)
        self.assertTrue('dummy-plugin' in commands)

    def test_plugin_list_commands(self):
        # plugin commands are present including a method and visualizer
        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')
        commands = command.list_commands(ctx=None)
        self.assertTrue('split-ints' in commands)
        self.assertTrue('mapping-viz' in commands)

        self.assertFalse('split_ints' in commands)
        self.assertFalse('mapping_viz' in commands)

    def test_action_parameter_types(self):
        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')
        results = self.runner.invoke(command, ['typical-pipeline', '--help'])
        help_text = results.output

        # Check the help text to make sure the types are displayed correctly
        # boolean primitive
        self.assertIn('--p-do-extra-thing / --p-no-do-extra-thing', help_text)
        # int primitive
        self.assertIn('--p-add INTEGER', help_text)

        # Run it to make sure the types are converted correctly, the framework
        # will error if it recieves the wrong type from the interface.
        self.runner.invoke(command, [
            'typical-pipeline', '--i-int-sequence', self.artifact1_path,
            '--i-mapping', self.mapping_path, '--p-do-extra-thing', '--p-add',
            '10', '--output-dir', os.path.join(self.tempdir, 'output-test')])

    def test_show_importable_types(self):
        result = self.runner.invoke(
            tools, ['import', '--show-importable-types'])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue('FourInts' in result.output)
        self.assertTrue('IntSequence1' in result.output)
        self.assertTrue('IntSequence2' in result.output)
        self.assertTrue('Kennel[Cat]' in result.output)
        self.assertTrue('Kennel[Dog]' in result.output)
        self.assertTrue('Mapping' in result.output)

    def test_show_importable_formats(self):
        result = self.runner.invoke(
            tools, ['import', '--show-importable-formats'])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue('FourIntsDirectoryFormat' in result.output)
        self.assertTrue('IntSequenceDirectoryFormat' in result.output)
        self.assertFalse('UnimportableFormat' in result.output)
        self.assertFalse('UnimportableDirectoryFormat' in result.output)
        self.assertTrue('MappingDirectoryFormat' in result.output)
        self.assertTrue('IntSequenceFormat' in result.output)
        self.assertTrue('IntSequenceFormatV2' in result.output)
        self.assertTrue('IntSequenceV2DirectoryFormat' in result.output)

    def test_extract(self):
        result = self.runner.invoke(
            tools, ['extract', self.artifact1_path, '--output-dir',
                    self.tempdir])
        # command completes sucessfully and creates the correct
        # output directory
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(os.path.exists(
            os.path.join(self.tempdir, self.artifact1_root_dir)))
        # results are correct
        data_f = open(os.path.join(self.tempdir, self.artifact1_root_dir,
                                   'data', 'ints.txt'))
        self.assertEqual(data_f.read(), "0\n42\n43\n")

    def test_validate_min(self):
        result = self.runner.invoke(
            tools, ['validate', self.artifact1_path, '--level', 'min'])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue('appears to be valid at level=min' in result.output)

    def test_validate_max(self):
        result = self.runner.invoke(
            tools, ['validate', self.artifact1_path, '--level', 'max'])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue('appears to be valid at level=max' in result.output)

        result = self.runner.invoke(tools, ['validate', self.artifact1_path])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue('appears to be valid at level=max' in result.output)

    def test_split_ints(self):
        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')

        # build output file names
        left_path = os.path.join(self.tempdir, 'left.qza')
        right_path = os.path.join(self.tempdir, 'right.qza')

        # TODO: currently must pass `--verbose` to commands invoked by Click's
        # test runner because redirecting stdout/stderr raises an
        # "io.UnsupportedOperation: fileno" error. Likely related to Click
        # mocking a filesystem in the test runner.
        result = self.runner.invoke(
            command, ['split-ints', '--i-ints', self.artifact1_path,
                      '--o-left', left_path, '--o-right', right_path,
                      '--verbose'])
        # command completes successfully and creates the correct
        # output files
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(os.path.exists(left_path))
        self.assertTrue(os.path.exists(right_path))
        # results are correct
        left = Artifact.load(left_path)
        right = Artifact.load(right_path)
        self.assertEqual(left.view(list), [0])
        self.assertEqual(right.view(list), [42, 43])

    def test_with_parameters_only(self):
        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')
        output_path = os.path.join(self.tempdir, 'output.qza')

        result = self.runner.invoke(
            command, ['params-only-method', '--p-name', 'Peanut', '--p-age',
                      '42', '--o-out', output_path, '--verbose'])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(os.path.exists(output_path))

        artifact = Artifact.load(output_path)
        self.assertEqual(artifact.view(dict), {'Peanut': '42'})

    def test_without_inputs_or_parameters(self):
        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')
        output_path = os.path.join(self.tempdir, 'output.qza')

        result = self.runner.invoke(
            command, ['no-input-method', '--o-out', output_path, '--verbose'])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(os.path.exists(output_path))

        artifact = Artifact.load(output_path)
        self.assertEqual(artifact.view(dict), {'foo': '42'})

    def test_qza_extension(self):
        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')

        # build output parameter arguments and expected output file names
        left_path = os.path.join(self.tempdir, 'left')
        expected_left_path = os.path.join(self.tempdir, 'left.qza')
        right_path = os.path.join(self.tempdir, 'right')
        expected_right_path = os.path.join(self.tempdir, 'right.qza')

        result = self.runner.invoke(
            command, ['split-ints', '--i-ints', self.artifact1_path,
                      '--o-left', left_path, '--o-right', right_path,
                      '--verbose'])
        # command completes successfully and creates the correct
        # output files
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(os.path.exists(expected_left_path))
        self.assertTrue(os.path.exists(expected_right_path))
        # results are correct
        left = Artifact.load(expected_left_path)
        right = Artifact.load(expected_right_path)
        self.assertEqual(left.view(list), [0])
        self.assertEqual(right.view(list), [42, 43])

    def test_qzv_extension(self):
        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')
        # build output parameter arguments and expected output file names
        viz_path = os.path.join(self.tempdir, 'viz')
        expected_viz_path = os.path.join(self.tempdir, 'viz.qzv')

        result = self.runner.invoke(
            command, ['most-common-viz', '--i-ints', self.artifact1_path,
                      '--o-visualization', viz_path, '--verbose'])
        # command completes successfully and creates the correct
        # output file
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(os.path.exists(expected_viz_path))
        # Visualization contains expected contents
        viz = Visualization.load(expected_viz_path)
        self.assertEqual(viz.get_index_paths(), {'html': 'data/index.html',
                                                 'tsv': 'data/index.tsv'})


class TestOptionalArtifactSupport(unittest.TestCase):
    def setUp(self):
        get_dummy_plugin()

        self.runner = CliRunner()
        self.plugin_command = RootCommand().get_command(
            ctx=None, name='dummy-plugin')
        self.tempdir = tempfile.mkdtemp(prefix='qiime2-q2cli-test-temp-')

        self.ints1 = os.path.join(self.tempdir, 'ints1.qza')
        Artifact.import_data(
            IntSequence1, [0, 42, 43], list).save(self.ints1)
        self.ints2 = os.path.join(self.tempdir, 'ints2.qza')
        Artifact.import_data(
            IntSequence1, [99, -22], list).save(self.ints2)
        self.ints3 = os.path.join(self.tempdir, 'ints3.qza')
        Artifact.import_data(
            IntSequence2, [43, 43], list).save(self.ints3)
        self.output = os.path.join(self.tempdir, 'output.qza')

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _run_command(self, *args):
        return self.runner.invoke(self.plugin_command, args)

    def test_no_optional_artifacts_provided(self):
        result = self._run_command(
            'optional-artifacts-method', '--i-ints', self.ints1,
            '--p-num1', 42, '--o-output', self.output, '--verbose')

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(Artifact.load(self.output).view(list),
                         [0, 42, 43, 42])

    def test_one_optional_artifact_provided(self):
        result = self._run_command(
            'optional-artifacts-method', '--i-ints', self.ints1,
            '--p-num1', 42, '--i-optional1', self.ints2,
            '--o-output', self.output, '--verbose')

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(Artifact.load(self.output).view(list),
                         [0, 42, 43, 42, 99, -22])

    def test_all_optional_artifacts_provided(self):
        result = self._run_command(
            'optional-artifacts-method', '--i-ints', self.ints1,
            '--p-num1', 42, '--i-optional1', self.ints2,
            '--i-optional2', self.ints3, '--p-num2', 111,
            '--o-output', self.output, '--verbose')

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(Artifact.load(self.output).view(list),
                         [0, 42, 43, 42, 99, -22, 43, 43, 111])

    def test_optional_artifact_type_mismatch(self):
        result = self._run_command(
            'optional-artifacts-method', '--i-ints', self.ints1,
            '--p-num1', 42, '--i-optional1', self.ints3,
            '--o-output', self.output, '--verbose')

        self.assertEqual(result.exit_code, 1)
        self.assertIn("'optional1' is not a subtype of IntSequence1",
                      str(result.output))


class MetadataTestsBase(unittest.TestCase):
    def setUp(self):
        get_dummy_plugin()
        self.runner = CliRunner()
        self.plugin_command = RootCommand().get_command(
            ctx=None, name='dummy-plugin')
        self.tempdir = tempfile.mkdtemp(prefix='qiime2-q2cli-test-temp-')

        self.input_artifact = os.path.join(self.tempdir, 'in.qza')
        Artifact.import_data(
            IntSequence1, [0, 42, 43], list).save(self.input_artifact)
        self.output_artifact = os.path.join(self.tempdir, 'out.qza')

        self.metadata_file1 = os.path.join(self.tempdir, 'metadata1.tsv')
        with open(self.metadata_file1, 'w') as f:
            f.write('id\tcol1\n0\tfoo\nid1\tbar\n')

        self.metadata_file2 = os.path.join(self.tempdir, 'metadata2.tsv')
        with open(self.metadata_file2, 'w') as f:
            f.write('id\tcol2\n0\tbaz\nid1\tbaa\n')

        self.metadata_artifact = os.path.join(self.tempdir, 'metadata.qza')
        Artifact.import_data(
            'Mapping', {'a': 'dog', 'b': 'cat'}).save(self.metadata_artifact)

        self.cmd_config = os.path.join(self.tempdir, 'conf.ini')
        with open(self.cmd_config, 'w') as f:
            f.write('[dummy-plugin.identity-with-metadata]\n'
                    'm-metadata-file=%s\n' % self.metadata_file1)
            f.write('[dummy-plugin.identity-with-optional-metadata]\n'
                    'm-metadata-file=%s\n' % self.metadata_file1)
            f.write('[dummy-plugin.identity-with-metadata-category]\n'
                    'm-metadata-file=%s\n'
                    'm-metadata-category=col1\n' % self.metadata_file1)
            f.write('[dummy-plugin.identity-with-optional-metadata-category]\n'
                    'm-metadata-file=%s\n'
                    'm-metadata-category=col1\n' % self.metadata_file1)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _run_command(self, *args):
        return self.runner.invoke(self.plugin_command, args)

    def _assertMetadataOutput(self, result, *, exp_tsv, exp_yaml):
        self.assertEqual(result.exit_code, 0)

        artifact = Artifact.load(self.output_artifact)
        action_dir = artifact._archiver.provenance_dir / 'action'

        if exp_tsv is None:
            self.assertFalse((action_dir / 'metadata.tsv').exists())
        else:
            with (action_dir / 'metadata.tsv').open() as fh:
                self.assertEqual(fh.read(), exp_tsv)

        with (action_dir / 'action.yaml').open() as fh:
            self.assertIn(exp_yaml, fh.read())


class TestMetadataSupport(MetadataTestsBase):
    def test_required_metadata_missing(self):
        result = self._run_command(
            'identity-with-metadata', '--i-ints', self.input_artifact,
            '--o-out', self.output_artifact)

        self.assertEqual(result.exit_code, 1)
        self.assertTrue(result.output.startswith('Usage:'))
        self.assertIn("Missing option: --m-metadata-file", result.output)

    def test_optional_metadata_missing(self):
        result = self._run_command(
            'identity-with-optional-metadata', '--i-ints', self.input_artifact,
            '--o-out', self.output_artifact, '--verbose')

        self._assertMetadataOutput(result, exp_tsv=None,
                                   exp_yaml='metadata: null')

    def test_single_metadata(self):
        for command in ('identity-with-metadata',
                        'identity-with-optional-metadata'):
            result = self._run_command(
                command, '--i-ints', self.input_artifact, '--o-out',
                self.output_artifact, '--m-metadata-file', self.metadata_file1,
                '--verbose')

            self._assertMetadataOutput(
                result, exp_tsv='id\tcol1\n0\tfoo\nid1\tbar\n',
                exp_yaml="metadata: !metadata 'metadata.tsv'")

    def test_multiple_metadata(self):
        for command in ('identity-with-metadata',
                        'identity-with-optional-metadata'):
            result = self._run_command(
                command, '--i-ints', self.input_artifact, '--o-out',
                self.output_artifact, '--m-metadata-file', self.metadata_file1,
                '--m-metadata-file', self.metadata_file2, '--m-metadata-file',
                self.metadata_artifact, '--verbose')

            exp_yaml = "metadata: !metadata '%s:metadata.tsv'" % (
                Artifact.load(self.metadata_artifact).uuid)
            self._assertMetadataOutput(
                result, exp_tsv='\tcol1\tcol2\ta\tb\n0\tfoo\tbaz\tdog\tcat\n',
                exp_yaml=exp_yaml)

    def test_invalid_metadata_merge(self):
        for command in ('identity-with-metadata',
                        'identity-with-optional-metadata'):
            result = self._run_command(
                command, '--i-ints', self.input_artifact, '--o-out',
                self.output_artifact, '--m-metadata-file', self.metadata_file1,
                '--m-metadata-file', self.metadata_file1)

            self.assertEqual(result.exit_code, -1)
            self.assertIn('overlapping categories', str(result.exception))

    def test_cmd_config_metadata(self):
        for command in ('identity-with-metadata',
                        'identity-with-optional-metadata'):
            result = self._run_command(
                command, '--i-ints', self.input_artifact, '--o-out',
                self.output_artifact, '--cmd-config', self.cmd_config,
                '--verbose')

            self._assertMetadataOutput(
                result, exp_tsv='id\tcol1\n0\tfoo\nid1\tbar\n',
                exp_yaml="metadata: !metadata 'metadata.tsv'")


class TestMetadataCategorySupport(MetadataTestsBase):
    def test_required_missing(self):
        result = self._run_command(
            'identity-with-metadata-category', '--i-ints', self.input_artifact,
            '--o-out', self.output_artifact)

        self.assertEqual(result.exit_code, 1)
        self.assertTrue(result.output.startswith('Usage:'))
        self.assertIn("Missing option: --m-metadata-file", result.output)
        self.assertIn("Missing option: --m-metadata-category", result.output)

    def test_optional_metadata_missing(self):
        result = self._run_command(
            'identity-with-optional-metadata-category', '--i-ints',
            self.input_artifact, '--o-out', self.output_artifact, '--verbose')

        self._assertMetadataOutput(result, exp_tsv=None,
                                   exp_yaml='metadata: null')

    def test_optional_metadata_without_category(self):
        result = self._run_command(
            'identity-with-optional-metadata-category', '--i-ints',
            self.input_artifact, '--o-out', self.output_artifact,
            '--m-metadata-file', self.metadata_file1)

        self.assertEqual(result.exit_code, 1)
        self.assertTrue(result.output.startswith('Usage:'))
        self.assertIn("Missing option: --m-metadata-category", result.output)

    def test_optional_category_without_metadata(self):
        result = self._run_command(
            'identity-with-optional-metadata-category', '--i-ints',
            self.input_artifact, '--o-out', self.output_artifact,
            '--m-metadata-category', 'col1')

        self.assertEqual(result.exit_code, 1)
        self.assertTrue(result.output.startswith('Usage:'))
        self.assertIn("Missing option: --m-metadata-file", result.output)

    def test_single_metadata(self):
        for command in ('identity-with-metadata-category',
                        'identity-with-optional-metadata-category'):
            result = self._run_command(
                command, '--i-ints', self.input_artifact, '--o-out',
                self.output_artifact, '--m-metadata-file', self.metadata_file1,
                '--m-metadata-category', 'col1', '--verbose')

            self._assertMetadataOutput(
                result, exp_tsv='0\tfoo\nid1\tbar\n',
                exp_yaml="metadata: !metadata 'metadata.tsv'")

    def test_multiple_metadata(self):
        for command in ('identity-with-metadata-category',
                        'identity-with-optional-metadata-category'):
            result = self._run_command(
                command, '--i-ints', self.input_artifact, '--o-out',
                self.output_artifact, '--m-metadata-file', self.metadata_file1,
                '--m-metadata-file', self.metadata_file2, '--m-metadata-file',
                self.metadata_artifact, '--m-metadata-category', 'col2',
                '--verbose')

            exp_yaml = "metadata: !metadata '%s:metadata.tsv'" % (
                Artifact.load(self.metadata_artifact).uuid)
            self._assertMetadataOutput(result, exp_tsv='0\tbaz\n',
                                       exp_yaml=exp_yaml)

    def test_multiple_metadata_category(self):
        result = self._run_command(
            'identity-with-metadata-category', '--i-ints',
            self.input_artifact, '--o-out', self.output_artifact,
            '--m-metadata-file', self.metadata_file1, '--m-metadata-file',
            self.metadata_file2, '--m-metadata-category', 'col1',
            '--m-metadata-category', 'col2')

        self.assertEqual(result.exit_code, 1)
        self.assertTrue(result.output.startswith('Usage:'))
        self.assertIn('--m-metadata-category was specified multiple times',
                      result.output)

    def test_invalid_metadata_merge(self):
        for command in ('identity-with-metadata-category',
                        'identity-with-optional-metadata-category'):
            result = self._run_command(
                command, '--i-ints', self.input_artifact, '--o-out',
                self.output_artifact, '--m-metadata-file', self.metadata_file1,
                '--m-metadata-file', self.metadata_file1,
                '--m-metadata-category', 'col1')

            self.assertEqual(result.exit_code, -1)
            self.assertIn('overlapping categories', str(result.exception))

    def test_cmd_config(self):
        for command in ('identity-with-metadata-category',
                        'identity-with-optional-metadata-category'):
            result = self._run_command(
                command, '--i-ints', self.input_artifact, '--o-out',
                self.output_artifact, '--cmd-config', self.cmd_config,
                '--verbose')

            self._assertMetadataOutput(
                result, exp_tsv='0\tfoo\nid1\tbar\n',
                exp_yaml="metadata: !metadata 'metadata.tsv'")
