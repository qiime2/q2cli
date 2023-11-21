# ----------------------------------------------------------------------------
# Copyright (c) 2016-2023, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import os
import gc
import re
import shutil
import unittest
from unittest.mock import patch
import tempfile
import zipfile
import bibtexparser as bp

from click.testing import CliRunner
from qiime2 import Artifact, Metadata
from qiime2.core.testing.util import get_dummy_plugin
from qiime2.metadata.base import SUPPORTED_COLUMN_TYPES
from qiime2.core.cache import Cache
from qiime2.sdk.result import Result
from qiime2.sdk.plugin_manager import PluginManager

from q2cli.util import load_metadata
from q2cli.builtin.tools import tools
from q2cli.commands import RootCommand
from q2cli.core.usage import ReplayCLIUsage


class TestCastMetadata(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.tempdir = tempfile.mkdtemp(prefix='qiime2-q2cli-test-temp-')

        self.metadata_file = os.path.join(
                self.tempdir, 'metadata.tsv')
        with open(self.metadata_file, 'w') as f:
            f.write('id\tnumbers\tstrings\n0\t42\tabc\n1\t-1.5\tdef')

        self.cast_metadata_dump = \
            ('id\tnumbers\tstrings\n#q2:types\tcategorical\tcategorical\n0\t42'
             '\tabc\n1\t-1.5\tdef\n\n')

        self.output_file = os.path.join(
                self.tempdir, 'test_output.tsv')

    def test_input_invalid_column_type(self):
        result = self.runner.invoke(
            tools, ['cast-metadata', self.metadata_file, '--cast',
                    'numbers:foo', '--output-file', self.output_file])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('Unknown column type provided.', result.output)

    def test_input_duplicate_columns(self):
        result = self.runner.invoke(
            tools, ['cast-metadata', self.metadata_file, '--cast',
                    'numbers:numerical', '--cast', 'numbers:categorical',
                    '--output-file', self.output_file])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            '"numbers" appears in cast more than once.', result.output)

    def test_input_invalid_cast_format_missing_colon(self):
        result = self.runner.invoke(
            tools, ['cast-metadata', self.metadata_file, '--cast', 'numbers',
                    '--output-file', self.output_file])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('Missing `:` in --cast numbers', result.output)

    def test_input_invalid_cast_format_extra_colon(self):
        result = self.runner.invoke(
            tools, ['cast-metadata', self.metadata_file, '--cast', 'numbers::',
                    '--output-file', self.output_file])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('Incorrect number of fields in --cast numbers::',
                      result.output)
        self.assertIn('Observed 3', result.output)

    def test_error_on_extra(self):
        result = self.runner.invoke(
            tools, ['cast-metadata', self.metadata_file, '--cast',
                    'extra:numeric', '--output-file', self.output_file])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "The following cast columns were not found within the"
            " metadata: extra", result.output)

    def test_error_on_missing(self):
        result = self.runner.invoke(
            tools, ['cast-metadata', self.metadata_file, '--cast',
                    'numbers:categorical', '--error-on-missing',
                    '--output-file', self.output_file])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "The following columns within the metadata"
            " were not provided in the cast: strings",
            result.output)

    def test_extra_columns_removed(self):
        result = self.runner.invoke(
            tools, ['cast-metadata', self.metadata_file, '--cast',
                    'numbers:categorical', '--cast', 'extra:numeric',
                    '--ignore-extra', '--output-file', self.output_file])

        self.assertEqual(result.exit_code, 0)
        casted_metadata = load_metadata(self.output_file)
        self.assertNotIn('extra', casted_metadata.columns.keys())

    def test_complete_successful_run(self):
        result = self.runner.invoke(
            tools, ['cast-metadata', self.metadata_file, '--cast',
                    'numbers:categorical', '--output-file', self.output_file])

        self.assertEqual(result.exit_code, 0)
        input_metadata = load_metadata(self.metadata_file)
        self.assertEqual('numeric', input_metadata.columns['numbers'].type)

        casted_metadata = load_metadata(self.output_file)
        self.assertEqual('categorical',
                         casted_metadata.columns['numbers'].type)

    def test_write_to_stdout(self):
        result = self.runner.invoke(
            tools, ['cast-metadata', self.metadata_file, '--cast',
                    'numbers:categorical'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(self.cast_metadata_dump, result.output)

    def test_valid_column_types(self):
        result = self.runner.invoke(tools, ['cast-metadata', '--help'])
        for col_type in SUPPORTED_COLUMN_TYPES:
            self.assertIn(col_type, result.output)


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

        self.ints2 = os.path.join(self.tempdir, 'ints')
        ints1.export_data(self.ints2)

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

    def test_export_to_file_creates_directories(self):
        output_path = os.path.join(self.tempdir, 'somewhere', 'output')
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

    def test_export_to_file_with_format_success_message(self):
        output_path = os.path.join(self.tempdir, 'output.int')
        result = self.runner.invoke(tools, [
            'export', '--input-path', self.ints1, '--output-path', output_path,
            '--output-format', 'IntSequenceFormatV2'
            ])
        success = 'Exported %s as IntSequenceFormatV2 to file %s\n' % (
                   self.ints1, output_path)
        self.assertEqual(success, result.output)

    def test_export_to_dir_without_format_success_message(self):
        output_path = os.path.join(self.tempdir, 'output')
        result = self.runner.invoke(tools, [
            'export', '--input-path', self.ints1, '--output-path', output_path
            ])
        success = 'Exported %s as IntSequenceDirectoryFormat to '\
                  'directory %s\n' % (self.ints1, output_path)
        self.assertEqual(success, result.output)

    def test_export_visualization_to_dir_success_message(self):
        output_path = os.path.join(self.tempdir, 'output')
        result = self.runner.invoke(tools, [
            'export', '--input-path', self.viz, '--output-path', output_path
        ])
        success = 'Exported %s as Visualization to '\
                  'directory %s\n' % (self.viz, output_path)
        self.assertEqual(success, result.output)

    def test_extract_to_dir_success_message(self):
        result = self.runner.invoke(tools, [
            'extract', '--input-path', self.ints1,
            '--output-path', self.tempdir
            ])
        success = 'Extracted %s to directory %s' % (self.ints1, self.tempdir)
        self.assertIn(success, result.output)

    def test_import_from_directory_without_format_success_message(self):
        output_path = os.path.join(self.tempdir, 'output.qza')
        result = self.runner.invoke(tools, [
            'import', '--input-path', self.ints2, '--type', 'IntSequence1',
            '--output-path', output_path
            ])
        success = 'Imported %s as IntSequenceDirectoryFormat to '\
                  '%s\n' % (self.ints2, output_path)
        self.assertEqual(success, result.output)

    def test_import_from_file_with_format_success_message(self):
        output_path = os.path.join(self.tempdir, 'output.qza')
        result = self.runner.invoke(tools, [
            'import', '--input-path', os.path.join(self.ints2, 'ints.txt'),
            '--type', 'IntSequence1',
            '--output-path', output_path,
            '--input-format', 'IntSequenceFormat'
        ])
        success = 'Imported %s as IntSequenceFormat to '\
                  '%s\n' % (os.path.join(self.ints2, 'ints.txt'), output_path)
        self.assertEqual(success, result.output)


class TestExportToFileFormat(TestInspectMetadata):
    def setUp(self):
        super().setUp()
        # Working directory is changed to temp directory to prevent cluttering
        # the repo directory with test files
        self.current_dir = os.getcwd()
        os.chdir(self.tempdir)

    def tearDown(self):
        super().tearDown()
        os.chdir(self.current_dir)

    def test_export_file_format(self):
        output_path = os.path.join(os.getcwd(), 'output')
        result = self.runner.invoke(tools, [
            'export', '--input-path', self.ints1, '--output-path', output_path,
            '--output-format', 'IntSequenceFormat'
        ])

        success = 'Exported %s as IntSequenceFormat to file %s\n' % \
                  (self.ints1, output_path)
        self.assertEqual(success, result.output)

    def test_export_dir_format(self):
        result = self.runner.invoke(tools, [
            'export', '--input-path', self.ints1, '--output-path', os.getcwd(),
            '--output-format', 'IntSequenceDirectoryFormat'
        ])

        success = 'Exported %s as IntSequenceDirectoryFormat to directory ' \
                  '%s\n' % (self.ints1, os.getcwd())
        self.assertEqual(success, result.output)

    def test_export_dir_format_nested(self):
        output_path = os.path.join(os.getcwd(), 'output')
        result = self.runner.invoke(tools, [
            'export', '--input-path', self.ints1, '--output-path', output_path,
            '--output-format', 'IntSequenceDirectoryFormat'
        ])

        success = 'Exported %s as IntSequenceDirectoryFormat to directory ' \
                  '%s\n' % (self.ints1, output_path)
        self.assertEqual(success, result.output)

    def test_export_to_filename_without_path(self):
        output_path = 'output'
        result = self.runner.invoke(tools, [
            'export', '--input-path', self.viz, '--output-path', output_path
        ])
        success = 'Exported %s as Visualization to '\
                  'directory %s\n' % (self.viz, output_path)
        self.assertEqual(success, result.output)


class TestImport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = CliRunner()

    def test_import_min_validate(self):
        with tempfile.TemporaryDirectory() as tempdir:
            fp = os.path.join(tempdir, 'ints.txt')
            with open(fp, 'w') as fh:
                for i in range(5):
                    fh.write(f'{i}\n')
                fh.write('a\n')

            out_fp = os.path.join(tempdir, 'out.qza')

            # import with min allows format error outside of min purview
            # (validate level min checks only first 5 items)
            result = self.runner.invoke(tools, [
                'import', '--type', 'IntSequence1', '--input-path', tempdir,
                '--output-path', out_fp, '--validate-level', 'min'
            ])
            self.assertEqual(result.exit_code, 0)

            # import with max should catch all format errors, max is default
            result = self.runner.invoke(tools, [
                'import', '--type', 'IntSequence1', '--input-path',
                tempdir, '--output-path', out_fp
            ])
            self.assertEqual(result.exit_code, 1)
            self.assertIn('Line 6 is not an integer', result.output)

        with tempfile.TemporaryDirectory() as tempdir:
            fp = os.path.join(tempdir, 'ints.txt')
            with open(fp, 'w') as fh:
                fh.write('1\n')
                fh.write('a\n')
                fh.write('3\n')

            out_fp = os.path.join(tempdir, 'out.qza')

            # import with min catches format errors within its purview
            result = self.runner.invoke(tools, [
                'import', '--type', 'IntSequence1', '--input-path',
                tempdir, '--output-path', out_fp, '--validate-level', 'min'
            ])
            self.assertEqual(result.exit_code, 1)
            self.assertIn('Line 2 is not an integer', result.output)


class TestCacheTools(unittest.TestCase):
    def setUp(self):
        get_dummy_plugin()

        self.runner = CliRunner()
        self.plugin_command = RootCommand().get_command(
            ctx=None, name='dummy-plugin')
        self.tempdir = \
            tempfile.TemporaryDirectory(prefix='qiime2-q2cli-test-temp-')

        self.art1 = Artifact.import_data('IntSequence1', [0, 1, 2])
        self.art2 = Artifact.import_data('IntSequence1', [3, 4, 5])
        self.art3 = Artifact.import_data('IntSequence1', [6, 7, 8])
        self.art4 = Artifact.import_data('IntSequence2', [9, 10, 11])
        self.to_import = os.path.join(self.tempdir.name, 'to_import')
        self.art1.export_data(self.to_import)
        self.cache = Cache(os.path.join(self.tempdir.name, 'new_cache'))

    def tearDown(self):
        self.tempdir.cleanup()

    def test_cache_create(self):
        cache_path = os.path.join(self.tempdir.name, 'created_cache')

        result = self.runner.invoke(
            tools, ['cache-create', '--cache', cache_path])

        success = "Created cache at '%s'\n" % cache_path
        self.assertEqual(success, result.output)
        self.assertTrue(Cache.is_cache(cache_path))

    def test_cache_remove(self):
        self.cache.save(self.art1, 'key')
        self.assertTrue('key' in self.cache.get_keys())

        result = self.runner.invoke(
            tools,
            ['cache-remove', '--cache', str(self.cache.path), '--key', 'key'])

        success = "Removed key 'key' from cache '%s'\n" % self.cache.path
        self.assertEqual(success, result.output)
        self.assertFalse('key' in self.cache.get_keys())

    def test_cache_garbage_collection(self):
        # Data referenced directly by key
        self.cache.save(self.art1, 'foo')
        # Data referenced by pool that is referenced by key
        pool = self.cache.create_pool(key='bar')
        pool.save(self.art2)
        # We will be manually deleting the keys that back these two
        self.cache.save(self.art3, 'baz')
        pool = self.cache.create_pool(key='qux')
        pool.save(self.art4)

        # What we expect to see before and after gc
        expected_pre_gc_contents = \
            set(('./VERSION', 'keys/foo', 'keys/bar',
                 'keys/baz', 'keys/qux',
                 f'pools/bar/{self.art2.uuid}',
                 f'pools/qux/{self.art4.uuid}',
                 f'data/{self.art1.uuid}', f'data/{self.art2.uuid}',
                 f'data/{self.art3.uuid}', f'data/{self.art4.uuid}'))

        expected_post_gc_contents = \
            set(('./VERSION', 'keys/foo', 'keys/bar',
                 f'pools/bar/{self.art2.uuid}',
                 f'data/{self.art1.uuid}', f'data/{self.art2.uuid}'))

        # Assert cache looks how we want pre gc
        pre_gc_contents = _get_cache_contents(self.cache)
        self.assertEqual(expected_pre_gc_contents, pre_gc_contents)

        # Delete keys
        self.cache.remove(self.cache.keys / 'baz')
        self.cache.remove(self.cache.keys / 'qux')

        # Make sure Python's garbage collector gets the process pool symlinks
        # to the artifact that was keyed on baz and the one in the qux pool
        gc.collect()
        result = self.runner.invoke(
            tools,
            ['cache-garbage-collection', '--cache', str(self.cache.path)])

        success = "Ran garbage collection on cache at '%s'\n" % self.cache.path
        self.assertEqual(success, result.output)

        # Assert cache looks how we want post gc
        post_gc_contents = _get_cache_contents(self.cache)
        self.assertEqual(expected_post_gc_contents, post_gc_contents)

    def test_cache_store(self):
        artifact = os.path.join(self.tempdir.name, 'artifact.qza')
        self.art1.save(artifact)

        result = self.runner.invoke(
            tools, ['cache-store', '--cache', str(self.cache.path),
                    '--artifact-path', artifact, '--key', 'key'])

        success = "Saved the artifact '%s' to the cache '%s' under the key " \
            "'key'\n" % (artifact, self.cache.path)
        self.assertEqual(success, result.output)

    def test_cache_fetch(self):
        artifact = os.path.join(self.tempdir.name, 'artifact.qza')
        self.cache.save(self.art1, 'key')

        result = self.runner.invoke(
            tools, ['cache-fetch', '--cache', str(self.cache.path),
                    '--key', 'key', '--output-path', artifact])

        success = "Loaded artifact with the key 'key' from the cache '%s' " \
            "and saved it to the file '%s'\n" % (self.cache.path, artifact)
        self.assertEqual(success, result.output)

    def test_cache_roundtrip(self):
        in_artifact = os.path.join(self.tempdir.name, 'in_artifact.qza')
        out_artifact = os.path.join(self.tempdir.name, 'out_artifact.qza')

        self.art1.save(in_artifact)

        result = self.runner.invoke(
            tools, ['cache-store', '--cache', str(self.cache.path),
                    '--artifact-path', in_artifact, '--key', 'key'])

        success = "Saved the artifact '%s' to the cache '%s' under the key " \
            "'key'\n" % (in_artifact, self.cache.path)
        self.assertEqual(success, result.output)

        result = self.runner.invoke(
            tools, ['cache-fetch', '--cache', str(self.cache.path),
                    '--key', 'key', '--output-path', out_artifact])

        success = "Loaded artifact with the key 'key' from the cache '%s' " \
            "and saved it to the file '%s'\n" % (self.cache.path, out_artifact)
        self.assertEqual(success, result.output)

        artifact = Artifact.load(out_artifact)
        self.assertEqual([0, 1, 2], artifact.view(list))

    def test_cache_status(self):
        success_template = \
            "Status of the cache at the path '%s':\n\n%s\n\n%s\n"

        # Empty cache
        result = self.runner.invoke(
            tools, ['cache-status', '--cache', str(self.cache.path)])
        success = \
            success_template % (str(self.cache.path), 'No data keys in cache',
                                'No pool keys in cache')
        self.assertEqual(success, result.output)

        # Cache with only data
        in_artifact = os.path.join(self.tempdir.name, 'in_artifact.qza')
        self.art1.save(in_artifact)
        self.runner.invoke(
            tools, ['cache-store', '--cache', str(self.cache.path),
                    '--artifact-path', in_artifact, '--key', 'key'])

        result = self.runner.invoke(
            tools, ['cache-status', '--cache', str(self.cache.path)])
        data_output = 'Data keys in cache:\ndata: key -> %s' % \
            str(Result.peek(self.cache.data / str(self.art1.uuid)))
        success = \
            success_template % (str(self.cache.path), data_output,
                                'No pool keys in cache')
        self.assertEqual(success, result.output)

        # Cache with data and pool
        pool = self.cache.create_pool(key='pool')
        pool.save(self.art2)

        result = self.runner.invoke(
            tools, ['cache-status', '--cache', str(self.cache.path)])
        pool_output = 'Pool keys in cache:\npool: pool -> size = 1'
        success = \
            success_template % (str(self.cache.path), data_output,
                                pool_output)
        self.assertEqual(success, result.output)

    def test_cache_import(self):
        self.max_diff = None
        result = self.runner.invoke(
            tools, ['cache-import', '--type', 'IntSequence1', '--input-path',
                    self.to_import, '--cache', f'{self.cache.path}', '--key',
                    'foo'])
        success = 'Imported %s as IntSequenceDirectoryFormat to %s:foo\n' % \
            (self.to_import, self.cache.path)
        self.assertEqual(success, result.output)


def _get_cache_contents(cache):
    """Gets contents of cache not including contents of the artifacts
    themselves relative to the root of the cache
    """
    cache_contents = set()

    rel_keys = os.path.relpath(cache.keys, cache.path)
    rel_data = os.path.relpath(cache.data, cache.path)
    rel_pools = os.path.relpath(cache.pools, cache.path)
    rel_cache = os.path.relpath(cache.path, cache.path)

    for key in os.listdir(cache.keys):
        cache_contents.add(os.path.join(rel_keys, key))

    for art in os.listdir(cache.data):
        cache_contents.add(os.path.join(rel_data, art))

    for pool in os.listdir(cache.pools):
        for link in os.listdir(os.path.join(cache.pools, pool)):
            cache_contents.add(os.path.join(rel_pools, pool, link))

    for elem in os.listdir(cache.path):
        if os.path.isfile(os.path.join(cache.path, elem)):
            cache_contents.add(os.path.join(rel_cache, elem))

    return cache_contents


class TestPeek(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.tempdir = tempfile.mkdtemp(prefix='qiime2-q2cli-test-temp-')

        # create artifact
        self.artifact = os.path.join(self.tempdir, 'artifact.qza')
        Artifact.import_data(
            'Mapping', {'foo': 'bar'}).save(self.artifact)

        # create visualization
        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')
        self.viz = os.path.join(self.tempdir, 'viz.qzv')

        self.ints = os.path.join(self.tempdir, 'ints.qza')
        ints = Artifact.import_data(
            'IntSequence1', [0, 42, 43], list)
        ints.save(self.ints)

        self.runner.invoke(
            command, ['most-common-viz', '--i-ints', self.ints,
                      '--o-visualization', self.viz, '--verbose'])

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_single_artifact(self):
        result = self.runner.invoke(tools, ['peek', self.artifact])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("UUID:", result.output)
        self.assertIn("Type:", result.output)
        self.assertIn("Data format:", result.output)
        self.assertEqual(result.output.count('\n'), 3)

    def test_single_visualization(self):
        result = self.runner.invoke(tools, ['peek', self.viz])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("UUID:", result.output)
        self.assertIn("Type:", result.output)
        self.assertNotIn("Data format:", result.output)
        self.assertEqual(result.output.count('\n'), 2)

    def test_artifact_and_visualization(self):
        result = self.runner.invoke(tools, ['peek', self.artifact, self.viz])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("UUID", result.output)
        self.assertIn("Type", result.output)
        self.assertIn("Data Format", result.output)
        self.assertIn("N/A", result.output)
        self.assertEqual(result.output.count('\n'), 3)

    def test_single_file_tsv(self):
        result = self.runner.invoke(tools, ['peek', '--tsv', self.artifact])
        self.assertIn("Filename\tType\tUUID\tData Format\n", result.output)
        self.assertIn("artifact.qza", result.output)
        self.assertEqual(result.output.count('\t'), 6)
        self.assertEqual(result.output.count('\n'), 2)

    def test_multiple_file_tsv(self):
        result = self.runner.invoke(tools, ['peek', '--tsv', self.artifact,
                                            self.viz])
        self.assertIn("Filename\tType\tUUID\tData Format\n", result.output)
        self.assertIn("artifact.qza", result.output)
        self.assertIn("viz.qzv", result.output)
        self.assertEqual(result.output.count('\t'), 9)
        self.assertEqual(result.output.count('\n'), 3)


class TestListTypes(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.pm = PluginManager()

    def tearDown(self):
        pass

    def test_list_all_types(self):
        result = self.runner.invoke(tools, ['list-types'])
        self.assertEqual(result.exit_code, 0)

        for name, artifact_class_record in self.pm.artifact_classes.items():
            self.assertIn(name, result.output)
            self.assertIn(artifact_class_record.description, result.output)

    def test_list_types_fuzzy(self):
        types = list(self.pm.artifact_classes)[:5]
        result = self.runner.invoke(tools, ['list-types', *types])
        self.assertEqual(result.exit_code, 0)

        # split on \n\n because types and their description are separated
        # by two newlines
        # len - 1 because split includes '' for the last \n\n split
        self.assertGreaterEqual(len(result.output.split('\n\n')) - 1,
                                len(types))

    def test_list_types_strict(self):
        types = list(self.pm.artifact_classes)[:5]
        result = self.runner.invoke(tools, ['list-types', '--strict', *types])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(len(result.output.split('\n\n')) - 1, len(types))

        result = self.runner.invoke(tools, ['list-types', '--strict',
                                            types[0] + 'x'])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(len(result.output), 0)

        result = self.runner.invoke(tools, ['list-types', '--strict', *types,
                                            types[0] + 'x'])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(len(result.output.split('\n\n')) - 1, len(types))

    def test_list_types_tsv(self):
        result = self.runner.invoke(tools, ['list-types', '--tsv'])
        self.assertEqual(result.exit_code, 0)

        # len - 1 because \n split produces a final ''
        self.assertEqual(len(result.output.split('\n')) - 1,
                         len(self.pm.artifact_classes))

        no_description_count = 0
        for name, artifact_class_record in self.pm.artifact_classes.items():
            self.assertIn(name, result.output)
            self.assertIn(artifact_class_record.description, result.output)
            if artifact_class_record.description == '':
                no_description_count += 1

        self.assertEqual(no_description_count, result.output.count('\t\n'))


class TestListFormats(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.pm = PluginManager()

    def tearDown(self):
        pass

    def test_list_all_importable_formats(self):
        result = self.runner.invoke(tools, ['list-formats', '--importable'])
        self.assertEqual(result.exit_code, 0)

        for name, format_record in self.pm.importable_formats.items():
            self.assertIn(name, result.output)
            docstring = format_record.format.__doc__
            if docstring:
                description = docstring.split('\n\n')[0].strip()
                for word in description:
                    self.assertIn(word.strip(), result.output)

    def test_list_all_exportable_formats(self):
        result = self.runner.invoke(tools, ['list-formats', '--exportable'])
        self.assertEqual(result.exit_code, 0)

        for name, format_record in self.pm.exportable_formats.items():
            self.assertIn(name, result.output)
            docstring = format_record.format.__doc__
            if docstring:
                description = docstring.split('\n\n')[0].strip()
                for word in description:
                    self.assertIn(word.strip(), result.output)

    def test_list_formats_fuzzy(self):
        formats = list(self.pm.importable_formats)[:5]
        result = self.runner.invoke(tools, ['list-formats', '--importable',
                                            *formats])
        self.assertEqual(result.exit_code, 0)

        # see TestListTypes.test_list_types_fuzzy
        self.assertGreaterEqual(len(result.output.split('\n\n')) - 1,
                                len(formats))

    def test_list_formats_strict(self):
        formats = list(self.pm.exportable_formats)[:5]
        result = self.runner.invoke(tools, ['list-formats', '--exportable',
                                            '--strict', *formats])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(len(result.output.split('\n\n')) - 1, len(formats))

        result = self.runner.invoke(tools, ['list-formats', '--exportable',
                                            '--strict', formats[0] + 'x'])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(len(result.output), 0)

        result = self.runner.invoke(tools, ['list-formats', '--exportable',
                                            '--strict', *formats,
                                            formats[0] + 'x'])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(len(result.output.split('\n\n')) - 1, len(formats))

    def test_list_formats_tsv(self):
        result = self.runner.invoke(tools, ['list-formats', '--importable',
                                            '--tsv'])
        self.assertEqual(result.exit_code, 0)

        # len - 1 because \n split produces a final ''
        self.assertEqual(len(result.output.split('\n')) - 1,
                         len(self.pm.importable_formats))

        no_description_count = 0
        for name, format_record in self.pm.importable_formats.items():
            self.assertIn(name, result.output)
            docstring = format_record.format.__doc__
            if docstring:
                description = docstring.split('\n\n')[0].strip()
                for word in description:
                    self.assertIn(word.strip(), result.output)

            if format_record.format.__doc__ is None:
                no_description_count += 1
        self.assertEqual(no_description_count, result.output.count('\t\n'))


class TestReplay(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.pm = PluginManager()
        self.dp = self.pm.plugins['dummy-plugin']
        self.tempdir = tempfile.mkdtemp(prefix='q2cli-test-replay-temp-')

        # contrive artifacts with different sorts of provenance
        int_seq1 = Artifact.import_data('IntSequence1', [1, 2, 3])
        int_seq2 = Artifact.import_data('IntSequence1', [4, 5, 6])
        int_seq3 = Artifact.import_data('IntSequence2', [7, 8])
        concat_ints = self.dp.actions['concatenate_ints']
        concated_ints, = concat_ints(int_seq1, int_seq2, int_seq3, 9, 0)
        concated_ints.save(os.path.join(self.tempdir, 'concated_ints.qza'))

        outer_dir = os.path.join(self.tempdir, 'outer_dir')
        inner_dir = os.path.join(self.tempdir, 'outer_dir', 'inner_dir')
        os.mkdir(outer_dir)
        os.mkdir(inner_dir)
        shutil.copy(os.path.join(self.tempdir, 'concated_ints.qza'), outer_dir)
        int_seq = Artifact.import_data('IntSequence1', [1, 2, 3, 4])
        left_ints, _ = self.dp.actions['split_ints'](int_seq)
        left_ints.save(os.path.join(inner_dir, 'left_ints.qza'))

        mapping = Artifact.import_data('Mapping', {'qiime': 2, 'triangle': 3})
        int_seq_with_md, = self.dp.actions['identity_with_metadata'](
            int_seq1,
            mapping.view(Metadata))
        int_seq_with_md.save(os.path.join(self.tempdir, 'int_seq_with_md.qza'))

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_replay_provenance(self):
        in_fp = os.path.join(self.tempdir, 'concated_ints.qza')
        out_fp = os.path.join(self.tempdir, 'rendered.txt')
        result = self.runner.invoke(
            tools,
            ['replay-provenance', '--in-fp', in_fp, '--out-fp', out_fp]
        )
        self.assertEqual(result.exit_code, 0)

        with open(out_fp, 'r') as fh:
            rendered = fh.read()

        self.assertIn('qiime tools import', rendered)
        self.assertIn('--type \'IntSequence1\'', rendered)
        self.assertIn('--type \'IntSequence2\'', rendered)
        self.assertIn('--input-path <your data here>', rendered)
        self.assertIn('--output-path int-sequence1-0.qza', rendered)
        self.assertIn('--output-path int-sequence1-1.qza', rendered)
        self.assertIn('--output-path int-sequence2-0.qza', rendered)

        self.assertIn('qiime dummy-plugin concatenate-ints', rendered)
        self.assertRegex(rendered, '--i-ints[12] int-sequence1-0.qza')
        self.assertRegex(rendered, '--i-ints[12] int-sequence1-1.qza')
        self.assertIn('--i-ints3 int-sequence2-0.qza', rendered)
        self.assertIn('--p-int1 9', rendered)
        self.assertIn('--p-int2 0', rendered)
        self.assertIn('--o-concatenated-ints concatenated-ints-0.qza',
                      rendered)

    def test_replay_provenance_python(self):
        in_fp = os.path.join(self.tempdir, 'concated_ints.qza')
        out_fp = os.path.join(self.tempdir, 'rendered.txt')
        result = self.runner.invoke(
            tools,
            ['replay-provenance', '--in-fp', in_fp, '--out-fp', out_fp,
                '--usage-driver', 'python3']
        )
        self.assertEqual(result.exit_code, 0)

        with open(out_fp, 'r') as fh:
            rendered = fh.read()

        self.assertIn('from qiime2 import Artifact', rendered)
        self.assertIn('Artifact.import_data', rendered)
        self.assertIn('dummy_plugin_actions.concatenate_ints', rendered)

    def test_replay_provenance_recurse(self):
        """
        If the directory is parsed recursively, both the concated_ints.qza and
        left_ints.qza will be captured.
        """
        in_fp = os.path.join(self.tempdir, 'outer_dir')
        out_fp = os.path.join(self.tempdir, 'rendered.txt')
        result = self.runner.invoke(
            tools,
            ['replay-provenance', '--in-fp', in_fp, '--out-fp', out_fp,
                '--usage-driver', 'python3', '--recurse']
        )
        self.assertEqual(result.exit_code, 0)

        with open(out_fp, 'r') as fh:
            rendered = fh.read()

        self.assertIn('dummy_plugin_actions.concatenate_ints', rendered)
        self.assertIn('dummy_plugin_actions.split_ints', rendered)

    def test_replay_provenance_use_md_without_parse(self):
        in_fp = os.path.join(self.tempdir, 'outer_dir')
        out_fp = os.path.join(self.tempdir, 'rendered.txt')
        result = self.runner.invoke(
            tools,
            ['replay-provenance', '--in-fp', in_fp, '--out-fp', out_fp,
             '--no-parse-metadata', '--use-recorded-metadata']
        )
        self.assertEqual(result.exit_code, 1)
        self.assertIsInstance(result.exception, ValueError)
        self.assertRegex(str(result.exception),
                         'Metadata not parsed for replay')

    @patch('qiime2.sdk.util.get_available_usage_drivers',
           return_value={'cli': ReplayCLIUsage})
    def test_replay_provenance_usage_driver_not_available(self, patch):
        in_fp = os.path.join(self.tempdir, 'concated_ints.qza')
        out_fp = os.path.join(self.tempdir, 'rendered.txt')
        result = self.runner.invoke(
            tools,
            ['replay-provenance', '--in-fp', in_fp, '--out-fp', out_fp,
                '--usage-driver', 'python3']
        )
        self.assertEqual(result.exit_code, 1)
        self.assertIsInstance(result.exception, ValueError)
        self.assertIn(
            'python3 usage driver is not available', str(result.exception)
        )

    def test_replay_citations(self):
        in_fp = os.path.join(self.tempdir, 'concated_ints.qza')
        out_fp = os.path.join(self.tempdir, 'citations.bib')
        result = self.runner.invoke(
            tools,
            ['replay-citations', '--in-fp', in_fp, '--out-fp', out_fp]
        )
        self.assertEqual(result.exit_code, 0)

        with open(out_fp) as fh:
            bib_database = bp.load(fh)

        # use .*? to non-greedily match version strings
        exp = [
            r'action\|dummy-plugin:.*?\|method:concatenate_ints\|0',
            r'framework\|qiime2:.*?\|0',
            r'plugin\|dummy-plugin:.*?\|0',
            r'plugin\|dummy-plugin:.*?\|1',
            r'transformer\|dummy-plugin:.*?\|builtins:list->'
            r'IntSequenceDirectoryFormat\|0',
            r'transformer\|dummy-plugin:.*?\|builtins:list->'
            r'IntSequenceV2DirectoryFormat\|4',
            r'transformer\|dummy-plugin:.*?\|builtins:list->'
            r'IntSequenceV2DirectoryFormat\|5',
            r'transformer\|dummy-plugin:.*?\|builtins:list->'
            r'IntSequenceV2DirectoryFormat|6',
            r'transformer\|dummy-plugin:.*?\|builtins:list->'
            r'IntSequenceV2DirectoryFormat\|8',
            r'view\|dummy-plugin:.*?\|IntSequenceDirectoryFormat\|0'
        ]

        self.assertEqual(len(exp), len(bib_database.entries))

        all_records_str = ''
        for record in bib_database.entries_dict.keys():
            all_records_str += f' {record}'
        for record in exp:
            self.assertRegex(all_records_str, record)

    def test_replay_citations_no_deduplicate(self):
        in_fp = os.path.join(self.tempdir, 'concated_ints.qza')
        out_fp = os.path.join(self.tempdir, 'citations.bib')
        result = self.runner.invoke(
            tools,
            ['replay-citations', '--in-fp', in_fp, '--out-fp', out_fp,
             '--no-deduplicate']
        )
        self.assertEqual(result.exit_code, 0)

        with open(out_fp) as fh:
            bib_database = bp.load(fh)
        self.assertEqual(28, len(bib_database.entries))

        with open(out_fp) as fh:
            file_contents = fh.read()
        framework_citations = \
            re.compile(r'framework\|qiime2:.*?\|0.*' * 4, re.DOTALL)
        self.assertRegex(file_contents, framework_citations)

    def test_replay_supplement(self):
        in_fp = os.path.join(self.tempdir, 'concated_ints.qza')
        out_fp = os.path.join(self.tempdir, 'supplement.zip')
        result = self.runner.invoke(
            tools,
            ['replay-supplement', '--in-fp', in_fp, '--out-fp', out_fp]
        )
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(zipfile.is_zipfile(out_fp))

        exp = {'python3_replay.py', 'cli_replay.sh', 'citations.bib'}
        with zipfile.ZipFile(out_fp, 'r') as zfh:
            self.assertEqual(exp, set(zfh.namelist()))

    def test_replay_supplement_with_metadata(self):
        in_fp = os.path.join(self.tempdir, 'int_seq_with_md.qza')
        out_fp = os.path.join(self.tempdir, 'supplement.zip')
        result = self.runner.invoke(
            tools,
            ['replay-supplement', '--in-fp', in_fp, '--out-fp', out_fp]
        )
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(zipfile.is_zipfile(out_fp))

        exp = {
            'python3_replay.py',
            'cli_replay.sh',
            'citations.bib',
            'recorded_metadata/',
            'recorded_metadata/dummy_plugin_identity_with_metadata_0/',
            'recorded_metadata/dummy_plugin_identity_with_metadata_0/'
            'metadata_0.tsv',
        }
        with zipfile.ZipFile(out_fp, 'r') as zfh:
            self.assertEqual(exp, set(zfh.namelist()))

    def test_replay_supplement_no_metadata_dump(self):
        in_fp = os.path.join(self.tempdir, 'int_seq_with_md.qza')
        out_fp = os.path.join(self.tempdir, 'supplement.zip')
        result = self.runner.invoke(
            tools,
            ['replay-supplement', '--in-fp', in_fp, '--out-fp', out_fp,
             '--no-dump-recorded-metadata']
        )
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(zipfile.is_zipfile(out_fp))

        not_exp = 'recorded_metadata/'
        with zipfile.ZipFile(out_fp, 'r') as zfh:
            self.assertNotIn(not_exp, set(zfh.namelist()))

    @patch('qiime2.sdk.util.get_available_usage_drivers', return_value={})
    def test_replay_supplement_usage_driver_not_available(self, patch):
        in_fp = os.path.join(self.tempdir, 'concated_ints.qza')
        out_fp = os.path.join(self.tempdir, 'rendered.txt')
        result = self.runner.invoke(
            tools,
            ['replay-supplement', '--in-fp', in_fp, '--out-fp', out_fp]
        )
        self.assertEqual(result.exit_code, 1)
        self.assertIsInstance(result.exception, ValueError)
        self.assertIn(
            'no available usage drivers', str(result.exception)
        )


if __name__ == "__main__":
    unittest.main()
