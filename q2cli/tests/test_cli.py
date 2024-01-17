# ----------------------------------------------------------------------------
# Copyright (c) 2016-2023, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import os.path
import unittest
import contextlib
import unittest.mock
import tempfile
import shutil
import click
import errno

from click.testing import CliRunner
from qiime2.core.cache import get_cache
from qiime2.core.testing.type import IntSequence1, IntSequence2, SingleInt
from qiime2.core.testing.util import get_dummy_plugin
from qiime2.sdk import Artifact, Visualization, ResultCollection

from q2cli.builtin.info import info
from q2cli.builtin.tools import tools
from q2cli.commands import RootCommand
from q2cli.click.type import QIIME2Type


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
        self.assertIn('other-plugin', result.output)

    def test_list_commands(self):
        # top level commands, including a plugin, are present
        qiime_cli = RootCommand()
        commands = qiime_cli.list_commands(ctx=None)
        self.assertIn('info', commands)
        self.assertIn('tools', commands)
        self.assertIn('dummy-plugin', commands)
        self.assertIn('other-plugin', commands)

    def test_plugin_list_commands(self):
        # plugin commands are present including a method and visualizer
        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')
        commands = command.list_commands(ctx=None)
        self.assertIn('split-ints', commands)
        self.assertIn('mapping-viz', commands)

        self.assertNotIn('split_ints', commands)
        self.assertNotIn('mapping_viz', commands)
        self.assertNotIn('-underscore-method', commands)
        self.assertNotIn('_underscore-method', commands)

    def test_plugin_list_hidden_commands(self):
        # plugin commands are present including a method and visualizer and
        # hidden method
        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')
        commands = self.runner.invoke(command,
                                      ['--show-hidden-actions']).output
        self.assertIn('split-ints', commands)
        self.assertIn('mapping-viz', commands)
        self.assertIn('_underscore-method', commands)

        self.assertNotIn('split_ints', commands)
        self.assertNotIn('mapping_viz', commands)
        self.assertNotIn('_underscore_method', commands)
        self.assertNotIn('-underscore-method', commands)

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
        output_dir = os.path.join(self.tempdir, 'output-test')
        result = self.runner.invoke(command, [
            'typical-pipeline', '--i-int-sequence', self.artifact1_path,
            '--i-mapping', self.mapping_path, '--p-do-extra-thing', '--p-add',
            '10', '--output-dir', output_dir, '--verbose'])
        self.assertEqual(result.exit_code, 0)

    def test_execute_hidden_action(self):
        int_path = os.path.join(self.tempdir, 'int.qza')
        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')
        result = self.runner.invoke(
                command, ['_underscore-method', '--o-int', int_path,
                          '--verbose'])

        self.assertEqual(result.exit_code, 0)

    def test_extract(self):
        result = self.runner.invoke(
            tools, ['extract', '--input-path', self.artifact1_path,
                    '--output-path', self.tempdir])
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
        self.assertIn('appears to be valid at level=min', result.output)

    def test_validate_max(self):
        result = self.runner.invoke(
            tools, ['validate', self.artifact1_path, '--level', 'max'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('appears to be valid at level=max', result.output)

        result = self.runner.invoke(tools, ['validate', self.artifact1_path])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('appears to be valid at level=max', result.output)

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

    def test_variadic_inputs(self):
        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')
        output_path = os.path.join(self.tempdir, 'output.qza')

        ints1 = Artifact.import_data('IntSequence1', [1, 2, 3]).save(
            os.path.join(self.tempdir, 'ints1.qza'))
        ints2 = Artifact.import_data('IntSequence2', [4, 5, 6]).save(
            os.path.join(self.tempdir, 'ints2.qza'))
        set1 = Artifact.import_data('SingleInt', 7).save(
            os.path.join(self.tempdir, 'set1.qza'))
        set2 = Artifact.import_data('SingleInt', 8).save(
            os.path.join(self.tempdir, 'set2.qza'))

        result = self.runner.invoke(
            command,
            ['variadic-input-method', '--i-ints', ints1, '--i-ints', ints2,
             '--i-int-set', set1, '--i-int-set', set2, '--p-nums', '9',
             '--p-nums', '10', '--p-opt-nums', '11', '--p-opt-nums', '12',
             '--p-opt-nums', '13', '--o-output', output_path, '--verbose'])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(os.path.exists(output_path))

        output = Artifact.load(output_path)
        self.assertEqual(output.view(list), list(range(1, 14)))

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

    def test_verbose_shows_stacktrace(self):
        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')
        output = os.path.join(self.tempdir, 'never-happens.qza')

        result = self.runner.invoke(
            command,
            ['failing-pipeline', '--i-int-sequence', self.artifact1_path,
             '--o-mapping', output, '--p-break-from', 'internal', '--verbose'])

        self.assertEqual(result.exit_code, 1)
        self.assertIn('Traceback (most recent call last)', result.output)

    def test_input_conversion(self):
        obj = QIIME2Type(IntSequence1.to_ast(), repr(IntSequence1))

        with self.assertRaisesRegex(click.exceptions.BadParameter,
                                    "x does not exist"):
            obj._convert_input('x', None, None)

        # This is to ensure the temp in the regex matches the temp used in the
        # method under test in type.py
        temp = str(get_cache().path)
        with unittest.mock.patch('qiime2.sdk.Result.peek',
                                 side_effect=OSError(errno.ENOSPC,
                                                     'No space left on '
                                                     'device')):
            with self.assertRaisesRegex(click.exceptions.BadParameter,
                                        f'{temp!r}.*'
                                        f'{self.artifact1_path!r}.*'
                                        f'{temp!r}'):
                obj._convert_input(self.artifact1_path, None, None)

    def test_syntax_error_in_env(self):
        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')

        viz_path = os.path.join(self.tempdir, 'viz')

        with unittest.mock.patch('qiime2.sdk.Result.peek',
                                 side_effect=SyntaxError):
            result = self.runner.invoke(
                command, ['most-common-viz', '--i-ints', self.artifact1_path,
                          '--o-visualization', viz_path, '--verbose'])

        self.assertEqual(result.exit_code, 1)
        self.assertIn('problem loading', result.output)
        self.assertIn(self.artifact1_path, result.output)

    def test_deprecated_help_text(self):
        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')

        result = self.runner.invoke(command, ['deprecated-method', '--help'])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('WARNING', result.output)
        self.assertIn('deprecated', result.output)

    def test_run_deprecated_gets_warning_msg(self):
        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')
        output_path = os.path.join(self.tempdir, 'output.qza')

        result = self.runner.invoke(
            command,
            ['deprecated-method', '--o-out', output_path, '--verbose'])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(os.path.exists(output_path))

        artifact = Artifact.load(output_path)

        # Just make sure that the command ran as expected
        self.assertEqual(artifact.view(dict), {'foo': '43'})

        self.assertIn('deprecated', result.output)


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
            '--p-num1', '42', '--o-output', self.output, '--verbose')

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(Artifact.load(self.output).view(list),
                         [0, 42, 43, 42])

    def test_one_optional_artifact_provided(self):
        result = self._run_command(
            'optional-artifacts-method', '--i-ints', self.ints1,
            '--p-num1', '42', '--i-optional1', self.ints2,
            '--o-output', self.output, '--verbose')

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(Artifact.load(self.output).view(list),
                         [0, 42, 43, 42, 99, -22])

    def test_all_optional_artifacts_provided(self):
        result = self._run_command(
            'optional-artifacts-method', '--i-ints', self.ints1,
            '--p-num1', '42', '--i-optional1', self.ints2,
            '--i-optional2', self.ints3, '--p-num2', '111',
            '--o-output', self.output, '--verbose')

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(Artifact.load(self.output).view(list),
                         [0, 42, 43, 42, 99, -22, 43, 43, 111])

    def test_optional_artifact_type_mismatch(self):
        result = self._run_command(
            'optional-artifacts-method', '--i-ints', self.ints1,
            '--p-num1', '42', '--i-optional1', self.ints3,
            '--o-output', self.output, '--verbose')

        self.assertEqual(result.exit_code, 1)
        self.assertRegex(str(result.output),
                         'type IntSequence1.*type IntSequence2.*')


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

        self.metadata_file_alt_id_header = os.path.join(
                self.tempdir, 'metadata-alt-id-header.tsv')
        with open(self.metadata_file_alt_id_header, 'w') as f:
            f.write('#SampleID\tcol1\n0\tfoo\nid1\tbar\n')

        self.metadata_file2 = os.path.join(self.tempdir, 'metadata2.tsv')
        with open(self.metadata_file2, 'w') as f:
            f.write('id\tcol2\n0\tbaz\nid1\tbaa\n')

        self.metadata_file_mixed_types = os.path.join(
                self.tempdir, 'metadata-mixed-types.tsv')
        with open(self.metadata_file_mixed_types, 'w') as f:
            f.write('id\tnumbers\tstrings\nid1\t42\tabc\nid2\t-1.5\tdef\n')

        self.metadata_artifact = os.path.join(self.tempdir, 'metadata.qza')
        Artifact.import_data(
            'Mapping', {'a': 'dog', 'b': 'cat'}).save(self.metadata_artifact)

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
        self.assertIn("Missing option '--m-metadata-file'", result.output)

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

            exp_tsv = 'id\tcol1\n#q2:types\tcategorical\n0\tfoo\nid1\tbar\n'
            self._assertMetadataOutput(
                result, exp_tsv=exp_tsv,
                exp_yaml="metadata: !metadata 'metadata.tsv'")

    def test_single_metadata_alt_id_header(self):
        # Test that the Metadata ID header is preserved, and not normalized to
        # 'id' (this used to be a bug). ID header normalization should only
        # happen when 2+ Metadata are being merged.
        for command in ('identity-with-metadata',
                        'identity-with-optional-metadata'):
            result = self._run_command(
                command, '--i-ints', self.input_artifact, '--o-out',
                self.output_artifact, '--m-metadata-file',
                self.metadata_file_alt_id_header, '--verbose')

            exp_tsv = (
                '#SampleID\tcol1\n'
                '#q2:types\tcategorical\n'
                '0\tfoo\n'
                'id1\tbar\n'
            )
            self._assertMetadataOutput(
                result, exp_tsv=exp_tsv,
                exp_yaml="metadata: !metadata 'metadata.tsv'")

    def test_multiple_metadata(self):
        for command in ('identity-with-metadata',
                        'identity-with-optional-metadata'):
            result = self._run_command(
                command, '--i-ints', self.input_artifact, '--o-out',
                self.output_artifact, '--m-metadata-file',
                self.metadata_file_alt_id_header, '--m-metadata-file',
                self.metadata_file2, '--m-metadata-file',
                self.metadata_artifact, '--verbose')

            exp_tsv = (
                'id\tcol1\tcol2\ta\tb\n'
                '#q2:types\tcategorical\tcategorical\tcategorical\tcategorical'
                '\n0\tfoo\tbaz\tdog\tcat\n'
            )
            exp_yaml = "metadata: !metadata '%s:metadata.tsv'" % (
                Artifact.load(self.metadata_artifact).uuid)
            self._assertMetadataOutput(result, exp_tsv=exp_tsv,
                                       exp_yaml=exp_yaml)

    def test_invalid_metadata_merge(self):
        for command in ('identity-with-metadata',
                        'identity-with-optional-metadata'):
            result = self._run_command(
                command, '--i-ints', self.input_artifact, '--o-out',
                self.output_artifact, '--m-metadata-file', self.metadata_file1,
                '--m-metadata-file', self.metadata_file1)

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn('overlapping columns', result.output)


class TestMetadataColumnSupport(MetadataTestsBase):
    # Neither md file or column params provided
    def test_required_missing_file_and_column(self):
        result = self._run_command(
            'identity-with-metadata-column', '--i-ints', self.input_artifact,
            '--o-out', self.output_artifact)

        self.assertEqual(result.exit_code, 1)
        self.assertTrue(result.output.startswith('Usage:'))
        self.assertIn("Missing option '--m-metadata-file'", result.output)

    # md file param missing, md column param & value provided
    def test_required_missing_file(self):
        result = self._run_command(
            'identity-with-metadata-column', '--i-ints', self.input_artifact,
            '--m-metadata-column', 'a', '--o-out', self.output_artifact)

        self.assertEqual(result.exit_code, 1)
        self.assertTrue(result.output.startswith('Usage:'))
        self.assertIn("Missing option '--m-metadata-file'", result.output)

    # md file param & value provided, md column param missing
    def test_required_missing_column(self):
        result = self._run_command(
            'identity-with-metadata-column', '--i-ints', self.input_artifact,
            '--m-metadata-file', self.metadata_file1,
            '--o-out', self.output_artifact)

        self.assertEqual(result.exit_code, 1)
        self.assertTrue(result.output.startswith('Usage:'))
        self.assertIn("Missing option '--m-metadata-column'", result.output)

    def test_optional_metadata_missing(self):
        result = self._run_command(
            'identity-with-optional-metadata-column', '--i-ints',
            self.input_artifact, '--o-out', self.output_artifact, '--verbose')

        self._assertMetadataOutput(result, exp_tsv=None,
                                   exp_yaml='metadata: null')

    def test_optional_metadata_without_column(self):
        result = self._run_command(
            'identity-with-optional-metadata-column', '--i-ints',
            self.input_artifact, '--o-out', self.output_artifact,
            '--m-metadata-file', self.metadata_file1)

        self.assertEqual(result.exit_code, 1)
        self.assertTrue(result.output.startswith('Usage:'))
        self.assertIn("Missing option '--m-metadata-column'", result.output)

    def test_optional_column_without_metadata(self):
        result = self._run_command(
            'identity-with-optional-metadata-column', '--i-ints',
            self.input_artifact, '--o-out', self.output_artifact,
            '--m-metadata-column', 'col1')

        self.assertEqual(result.exit_code, 1)
        self.assertTrue(result.output.startswith('Usage:'))
        self.assertIn("Missing option '--m-metadata-file'", result.output)

    def test_single_metadata(self):
        for command in ('identity-with-metadata-column',
                        'identity-with-optional-metadata-column'):
            result = self._run_command(
                command, '--i-ints', self.input_artifact, '--o-out',
                self.output_artifact, '--m-metadata-file', self.metadata_file1,
                '--m-metadata-column', 'col1', '--verbose')

            exp_tsv = 'id\tcol1\n#q2:types\tcategorical\n0\tfoo\nid1\tbar\n'
            if result.exit_code != 0:
                raise ValueError(result.exception)
            self._assertMetadataOutput(
                result, exp_tsv=exp_tsv,
                exp_yaml="metadata: !metadata 'metadata.tsv'")

    def test_multiple_metadata(self):
        for command in ('identity-with-metadata-column',
                        'identity-with-optional-metadata-column'):
            result = self._run_command(
                command, '--i-ints', self.input_artifact, '--o-out',
                self.output_artifact, '--m-metadata-file', self.metadata_file1,
                '--m-metadata-file', self.metadata_file2, '--m-metadata-file',
                self.metadata_artifact, '--m-metadata-column', 'col2',
                '--verbose')

            self.assertEqual(result.exit_code, 1)
            self.assertIn('\'--m-metadata-file\' was specified multiple times',
                          result.output)

    def test_multiple_metadata_column(self):
        result = self._run_command(
            'identity-with-metadata-column', '--i-ints',
            self.input_artifact, '--o-out', self.output_artifact,
            '--m-metadata-file', self.metadata_file1, '--m-metadata-file',
            self.metadata_file2, '--m-metadata-column', 'col1',
            '--m-metadata-column', 'col2')

        self.assertEqual(result.exit_code, 1)
        self.assertTrue(result.output.startswith('Usage:'))
        self.assertIn('\'--m-metadata-file\' was specified multiple times',
                      result.output)

    def test_categorical_metadata_column(self):
        result = self._run_command(
            'identity-with-categorical-metadata-column', '--help')
        help_text = result.output

        self.assertIn(
            '--m-metadata-column COLUMN  MetadataColumn[Categorical]',
            help_text)

        result = self._run_command(
            'identity-with-categorical-metadata-column', '--i-ints',
            self.input_artifact, '--o-out', self.output_artifact,
            '--m-metadata-file', self.metadata_file_mixed_types,
            '--m-metadata-column', 'strings', '--verbose')

        exp_tsv = 'id\tstrings\n#q2:types\tcategorical\nid1\tabc\nid2\tdef\n'
        self._assertMetadataOutput(
            result, exp_tsv=exp_tsv,
            exp_yaml="metadata: !metadata 'metadata.tsv'")

    def test_categorical_metadata_column_type_mismatch(self):
        result = self._run_command(
            'identity-with-categorical-metadata-column', '--i-ints',
            self.input_artifact, '--o-out', self.output_artifact,
            '--m-metadata-file', self.metadata_file_mixed_types,
            '--m-metadata-column', 'numbers')

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Metadata column", result.output)
        self.assertIn("numeric", result.output)
        self.assertIn("expected Categorical", result.output)

    def test_numeric_metadata_column(self):
        result = self._run_command(
            'identity-with-numeric-metadata-column', '--help')
        help_text = result.output

        self.assertIn('--m-metadata-column COLUMN  MetadataColumn[Numeric]',
                      help_text)

        result = self._run_command(
            'identity-with-numeric-metadata-column', '--i-ints',
            self.input_artifact, '--o-out', self.output_artifact,
            '--m-metadata-file', self.metadata_file_mixed_types,
            '--m-metadata-column', 'numbers', '--verbose')

        exp_tsv = 'id\tnumbers\n#q2:types\tnumeric\nid1\t42\nid2\t-1.5\n'
        self._assertMetadataOutput(
            result, exp_tsv=exp_tsv,
            exp_yaml="metadata: !metadata 'metadata.tsv'")

    def test_numeric_metadata_column_type_mismatch(self):
        result = self._run_command(
            'identity-with-numeric-metadata-column', '--i-ints',
            self.input_artifact, '--o-out', self.output_artifact,
            '--m-metadata-file', self.metadata_file_mixed_types,
            '--m-metadata-column', 'strings')

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Metadata column", result.output)
        self.assertIn("categorical", result.output)
        self.assertIn("expected Numeric", result.output)


class TestCollectionSupport(unittest.TestCase):
    def setUp(self):
        get_dummy_plugin()
        self.runner = CliRunner()
        self.plugin_command = RootCommand().get_command(
            ctx=None, name='dummy-plugin')
        self.tempdir = tempfile.mkdtemp(prefix='qiime2-q2cli-test-temp-')

        self.art1_path = os.path.join(self.tempdir, 'art1.qza')
        self.art2_path = os.path.join(self.tempdir, 'art2.qza')
        self.art1 = Artifact.import_data(SingleInt, 0)
        self.art2 = Artifact.import_data(SingleInt, 1)

        self.output = os.path.join(self.tempdir, 'out')
        self.output2 = os.path.join(self.tempdir, 'out2')

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _run_command(self, *args):
        return self.runner.invoke(self.plugin_command, args)

    def test_collection_roundtrip_list(self):
        result = self._run_command(
            'list-params', '--p-ints', '0', '--p-ints', '1', '--o-output',
            self.output, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = ResultCollection.load(self.output)

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['0', '1'])

        result = self._run_command(
            'list-of-ints', '--i-ints', self.output, '--o-output',
            self.output2, '--verbose'
        )

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['0', '1'])

    def test_collection_roundtrip_dict_keyed(self):
        result = self._run_command(
            'dict-params', '--p-ints', 'foo:0', '--p-ints', 'bar:1',
            '--o-output', self.output, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = ResultCollection.load(self.output)

        self.assertEqual(collection['foo'].view(int), 0)
        self.assertEqual(collection['bar'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['foo', 'bar'])

        result = self._run_command(
            'dict-of-ints', '--i-ints', self.output, '--o-output',
            self.output2, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = ResultCollection.load(self.output)

        self.assertEqual(collection['foo'].view(int), 0)
        self.assertEqual(collection['bar'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['foo', 'bar'])

    def test_collection_roundtrip_dict_unkeyed(self):
        result = self._run_command(
            'dict-params', '--p-ints', '0', '--p-ints', '1',
            '--o-output', self.output, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = ResultCollection.load(self.output)

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['0', '1'])

        result = self._run_command(
            'dict-of-ints', '--i-ints', self.output, '--o-output',
            self.output2, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = ResultCollection.load(self.output)

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['0', '1'])

    def test_de_facto_list(self):
        self.art1.save(self.art1_path)
        self.art2.save(self.art2_path)

        result = self._run_command(
            'list-of-ints', '--i-ints', self.art1_path, '--i-ints',
            self.art2_path, '--o-output', self.output, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = ResultCollection.load(self.output)

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['0', '1'])

    def test_de_facto_dict_keyed(self):
        self.art1.save(self.art1_path)
        self.art2.save(self.art2_path)

        result = self._run_command(
            'dict-of-ints', '--i-ints', f'foo:{self.art1_path}', '--i-ints',
            f'bar:{self.art2_path}', '--o-output', self.output, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = ResultCollection.load(self.output)

        self.assertEqual(collection['foo'].view(int), 0)
        self.assertEqual(collection['bar'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['foo', 'bar'])

    def test_de_facto_dict_unkeyed(self):
        self.art1.save(self.art1_path)
        self.art2.save(self.art2_path)

        result = self._run_command(
            'dict-of-ints', '--i-ints', self.art1_path, '--i-ints',
            self.art2_path, '--o-output', self.output, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = ResultCollection.load(self.output)

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['0', '1'])

    def test_mixed_keyed_unkeyed_inputs(self):
        self.art1.save(self.art1_path)
        self.art2.save(self.art2_path)

        result = self._run_command(
            'dict-of-ints', '--i-ints', f'foo:{self.art1_path}', '--i-ints',
            self.art2_path, '--o-output', self.output, '--verbose'
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn('Keyed values cannot be mixed with unkeyed values.',
                      str(result.exception))

        result = self._run_command(
            'dict-of-ints', '--i-ints', self.art1_path, '--i-ints',
            f'bar:{self.art2_path}', '--o-output', self.output, '--verbose'
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn('Keyed values cannot be mixed with unkeyed values.',
                      str(result.exception))

    def test_mixed_keyed_unkeyed_params(self):
        result = self._run_command(
            'dict-params', '--p-ints', 'foo:0', '--p-ints', '1',
            '--o-output', self.output, '--verbose'
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn('The unkeyed value <1> has been mixed with keyed values.'
                      ' All values must be keyed or unkeyed',
                      str(result.exception))

        result = self._run_command(
            'dict-params', '--p-ints', '0', '--p-ints', 'bar:1',
            '--o-output', self.output, '--verbose'
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn('The keyed value <bar:1> has been mixed with unkeyed'
                      ' values. All values must be keyed or unkeyed',
                      str(result.exception))

    def test_keyed_path_with_tilde(self):
        self.art1.save(self.art1_path)
        self.art2.save(self.art2_path)

        tmp = tempfile.gettempdir()
        tempdir = os.path.basename(self.tempdir)

        with modified_environ(HOME=tmp):
            result = self._run_command(
                'dict-of-ints',
                '--i-ints', f'foo:{os.path.join("~", tempdir, "art1.qza")}',
                '--i-ints', f'bar:{os.path.join("~", tempdir, "art2.qza")}',
                '--o-output', self.output, '--verbose')

        self.assertEqual(result.exit_code, 0)
        collection = ResultCollection.load(self.output)

        self.assertEqual(collection['foo'].view(int), 0)
        self.assertEqual(collection['bar'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['foo', 'bar'])

    def test_directory_with_non_artifacts(self):
        input_dir = os.path.join(self.tempdir, 'in')
        os.mkdir(input_dir)

        artifact_path = os.path.join(input_dir, 'a.qza')
        artifact = Artifact.import_data(IntSequence1, [0, 42, 43])
        artifact.save(artifact_path)

        with open(os.path.join(input_dir, 'bad.txt'), 'w') as fh:
            fh.write('This file is not an artifact')

        result = self._run_command(
            'list-of-ints', '--i-ints', input_dir, '--o-output',
            self.output, '--verbose'
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Invalid value for '--i-ints':", result.output)

    def test_empty_directory(self):
        result = self._run_command(
            'list-of-ints', '--i-ints', self.tempdir, '--o-output',
            self.output, '--verbose'
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn(f"Provided directory '{self.tempdir}' is empty.",
                      result.output)


@contextlib.contextmanager
def modified_environ(*remove, **update):
    """
    Taken from: https://stackoverflow.com/a/34333710.

    Updating the os.environ dict only modifies the environment variables from
    the perspective of the current Python process, so this isn't dangerous at
    all.

    Temporarily updates the ``os.environ`` dictionary in-place.

    The ``os.environ`` dictionary is updated in-place so that the modification
    is sure to work in all situations.

    :param remove: Environment variables to remove.
    :param update: Dictionary of environment variables and values to
                   add/update.
    """
    env = os.environ
    update = update or {}
    remove = remove or []

    # List of environment variables being updated or removed.
    stomped = (set(update.keys()) | set(remove)) & set(env.keys())
    # Environment variables and values to restore on exit.
    update_after = {k: env[k] for k in stomped}
    # Environment variables and values to remove on exit.
    remove_after = frozenset(k for k in update if k not in env)

    try:
        env.update(update)
        [env.pop(k, None) for k in remove]
        yield
    finally:
        env.update(update_after)
        [env.pop(k) for k in remove_after]


if __name__ == "__main__":
    unittest.main()
