# ----------------------------------------------------------------------------
# Copyright (c) 2016-2026, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import os
import gc
import re
import yaml
import pytest
import shutil
import unittest
from unittest.mock import patch
import tempfile
import zipfile
import bibtexparser as bp

from click.testing import CliRunner
from rachis import Artifact, Metadata
from rachis.core.testing.util import get_dummy_plugin
from rachis.core.testing.type import IntSequence1, IntSequence2, SingleInt
from rachis.metadata.base import SUPPORTED_COLUMN_TYPES
from rachis.core.cache import Cache
from rachis.sdk.result import Result
from rachis.sdk.plugin_manager import PluginManager
from rachis.core.annotate import Note

from rachis_cli.util import load_metadata, get_cli_command_names
from rachis_cli.builtin.tools import tools
from rachis_cli.commands import RootCommand
from rachis_cli.core.usage import ReplayCLIUsage


class TestCastMetadata(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.tempdir = tempfile.mkdtemp(prefix='rachis-cli-test-temp-')

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
        self.tempdir = tempfile.mkdtemp(prefix='rachis-cli-test-temp-')

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
        self.assertIn("IntSequence1 cannot be viewed as rachis metadata",
                      result.output)

    def test_visualization(self):
        # make a viz first:
        rachis_cli = RootCommand()
        command = rachis_cli.get_command(ctx=None, name='dummy-plugin')
        # build output parameter arguments and expected output file names
        viz_path = os.path.join(self.tempdir, 'viz.qzv')
        result = self.runner.invoke(
            command, ['most-common-viz', '--i-ints', self.ints1,
                      '--o-visualization', viz_path, '--verbose'])

        result = self.runner.invoke(tools, ['inspect-metadata', viz_path])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Visualizations cannot be viewed as rachis metadata",
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

        cls.tempdir = tempfile.mkdtemp(prefix='rachis-cli-test-temp-')

        cls.in_dir1 = os.path.join(cls.tempdir, 'input1')
        os.mkdir(cls.in_dir1)
        with open(os.path.join(cls.in_dir1, 'ints.txt'), 'w') as fh:
            for i in range(5):
                fh.write(f'{i}\n')
            fh.write('a\n')

        cls.in_dir2 = os.path.join(cls.tempdir, 'input2')
        os.mkdir(cls.in_dir2)
        with open(os.path.join(cls.in_dir2, 'ints.txt'), 'w') as fh:
            fh.write('1\n')
            fh.write('a\n')
            fh.write('3\n')

        cls.cache = Cache(os.path.join(cls.tempdir, 'new_cache'))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tempdir)

    def test_import_min_validate(self):
        out_fp = os.path.join(self.tempdir, 'out1.qza')

        # import with min allows format error outside of min purview
        # (validate level min checks only first 5 items)
        result = self.runner.invoke(tools, [
            'import', '--type', 'IntSequence1', '--input-path', self.in_dir1,
            '--output-path', out_fp, '--validate-level', 'min'
        ])
        self.assertEqual(result.exit_code, 0)

        # import with max should catch all format errors, max is default
        result = self.runner.invoke(tools, [
            'import', '--type', 'IntSequence1', '--input-path',
            self.in_dir1, '--output-path', out_fp
        ])
        self.assertEqual(result.exit_code, 1)
        self.assertIn('Line 6 is not an integer', result.output)

        out_fp = os.path.join(self.tempdir, 'out2.qza')

        # import with min catches format errors within its purview
        result = self.runner.invoke(tools, [
            'import', '--type', 'IntSequence1', '--input-path',
            self.in_dir2, '--output-path', out_fp, '--validate-level', 'min'
        ])
        self.assertEqual(result.exit_code, 1)
        self.assertIn('Line 2 is not an integer', result.output)

    def test_cache_import_min_validate(self):
        # import with min allows format error outside of min purview
        # (validate level min checks only first 5 items)
        result = self.runner.invoke(tools, [
            'cache-import', '--type', 'IntSequence1', '--input-path',
            self.in_dir1, '--cache', str(self.cache.path), '--key', 'foo',
            '--validate-level', 'min'
        ])
        self.assertEqual(result.exit_code, 0)

        # import with max should catch all format errors, max is default
        result = self.runner.invoke(tools, [
            'cache-import', '--type', 'IntSequence1', '--input-path',
            self.in_dir1, '--cache', str(self.cache.path), '--key', 'foo'
        ])
        self.assertEqual(result.exit_code, 1)
        self.assertIn('Line 6 is not an integer', result.output)

        # import with min catches format errors within its purview
        result = self.runner.invoke(tools, [
            'cache-import', '--type', 'IntSequence1', '--input-path',
            self.in_dir2, '--cache', str(self.cache.path), '--key', 'foo',
            '--validate-level', 'min'
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
            tempfile.TemporaryDirectory(prefix='rachis-cli-test-temp-')

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

        success = \
            f"Removed key 'key' from cache '{str(self.cache.path)}'\n" \
            f"Removed key(s) '('key',)' from cache '{str(self.cache.path)}'\n"
        self.assertEqual(success, result.output)
        self.assertFalse('key' in self.cache.get_keys())

    def test_cache_remove_multiple(self):
        self.cache.save(self.art1, 'key3')
        self.cache.save(self.art1, 'key2')
        self.cache.save(self.art1, 'key1')

        keys = self.cache.get_keys()
        self.assertEqual(['key1', 'key2', 'key3'], keys)

        result = self.runner.invoke(
            tools,
            ['cache-remove', '--cache', str(self.cache.path), '--key', 'key1',
             '--key', 'key2']
        )

        success = \
            f"Removed key 'key1' from cache '{str(self.cache.path)}'\n" \
            f"Removed key 'key2' from cache '{str(self.cache.path)}'\n" \
            "Removed key(s) '('key1', 'key2')' from cache " \
            f"'{str(self.cache.path)}'\n"

        new_keys = self.cache.get_keys()

        self.assertEqual(success, result.output)
        self.assertFalse('key1' in new_keys)
        self.assertFalse('key2' in new_keys)
        self.assertTrue('key3' in new_keys)

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
        self.tempdir = tempfile.mkdtemp(prefix='rachis-cli-test-temp-')

        # create artifact
        self.artifact = os.path.join(self.tempdir, 'artifact.qza')
        Artifact.import_data(
            'Mapping', {'foo': 'bar'}).save(self.artifact)

        # create visualization
        rachis_cli = RootCommand()
        command = rachis_cli.get_command(ctx=None, name='dummy-plugin')
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
        self.tempdir = tempfile.mkdtemp(prefix='rachis-cli-test-replay-temp-')

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

        mapping = Artifact.import_data('Mapping', {'rachis': 2, 'triangle': 3})
        int_seq_with_md, = self.dp.actions['identity_with_metadata'](
            int_seq1,
            mapping.view(Metadata))
        int_seq_with_md.save(os.path.join(self.tempdir, 'int_seq_with_md.qza'))

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_replay_provenance_cache(self):
        cache = Cache(os.path.join(self.tempdir, 'cache'))
        int_seq1 = Artifact.import_data('IntSequence1', [1, 2, 3])
        cache.save(int_seq1, 'int_seq1')
        cache_fp = os.path.join(self.tempdir, 'cache:int_seq1')

        self.runner.invoke(
            tools,
            ['replay-provenance', 'in-fp', cache_fp, '--out-fp', self.tempdir]
        )

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

        self.assertIn('rachis tools import', rendered)
        self.assertIn('--type \'IntSequence1\'', rendered)
        self.assertIn('--type \'IntSequence2\'', rendered)
        self.assertIn('--input-path <your data here>', rendered)
        self.assertIn('--output-path int-sequence1-0.qza', rendered)
        self.assertIn('--output-path int-sequence1-1.qza', rendered)
        self.assertIn('--output-path int-sequence2-0.qza', rendered)

        self.assertIn('rachis dummy-plugin concatenate-ints', rendered)
        self.assertRegex(rendered, '--i-ints[12] int-sequence1-0.qza')
        self.assertRegex(rendered, '--i-ints[12] int-sequence1-1.qza')
        self.assertIn('--i-ints3 int-sequence2-0.qza', rendered)
        self.assertIn('--p-int1 9', rendered)
        self.assertIn('--p-int2 0', rendered)
        self.assertIn('--o-concatenated-ints concatenated-ints-0.qza',
                      rendered)

    def test_replay_provenance_base_command(self):
        in_fp = os.path.join(self.tempdir, 'concated_ints.qza')

        for base_command in get_cli_command_names():
            with self.subTest(base_command=base_command):
                out_fp = os.path.join(
                    self.tempdir, '%s_rendered.txt' % base_command)
                result = self.runner.invoke(
                    tools,
                    ['replay-provenance', '--in-fp', in_fp,
                     '--out-fp', out_fp],
                    prog_name=base_command
                )
                self.assertEqual(result.exit_code, 0)

                with open(out_fp, 'r') as fh:
                    rendered = fh.read()

                self.assertIn('%s tools import' % base_command, rendered)
                self.assertIn(
                    '%s dummy-plugin concatenate-ints' % base_command,
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

        self.assertIn('from rachis import Artifact', rendered)
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

    @patch('rachis.sdk.util.get_available_usage_drivers',
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
            r'framework\|rachis:.*?\|0',
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
            re.compile(r'framework\|rachis:.*?\|0.*' * 4, re.DOTALL)
        self.assertRegex(file_contents, framework_citations)

    def test_replay_citations_cache(self):
        cache = Cache(os.path.join(self.tempdir, 'cache'))
        int_seq1 = Artifact.import_data('IntSequence1', [1, 2, 3])
        cache.save(int_seq1, 'int_seq1')
        cache_fp = os.path.join(self.tempdir, 'cache:int_seq1')

        self.runner.invoke(
            tools,
            ['replay-citations', 'in-fp', cache_fp, '--out-fp', self.tempdir]
        )

    def test_replay_supplement(self):
        in_fp = os.path.join(self.tempdir, 'concated_ints.qza')
        out_fp = os.path.join(self.tempdir, 'supplement.zip')
        result = self.runner.invoke(
            tools,
            ['replay-supplement', '--in-fp', in_fp, '--out-fp', out_fp]
        )
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(zipfile.is_zipfile(out_fp))

        exp = {
            'supplement/',
            'supplement/python3_replay.py',
            'supplement/cli_replay.sh',
            'supplement/citations.bib'
        }
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
            'supplement/',
            'supplement/python3_replay.py',
            'supplement/cli_replay.sh',
            'supplement/citations.bib',
            'supplement/recorded_metadata/',
            'supplement/recorded_metadata/'
            'dummy_plugin_identity_with_metadata_0/',
            'supplement/recorded_metadata/'
            'dummy_plugin_identity_with_metadata_0/metadata_0.tsv',
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

    @patch('rachis.sdk.util.get_available_usage_drivers', return_value={})
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

    def test_replay_supplement_zipfile(self):
        with tempfile.TemporaryDirectory() as tempdir:
            in_fp = os.path.join(self.tempdir, 'concated_ints.qza')
            out_fp = os.path.join(tempdir, 'supplement.zip')

            result = self.runner.invoke(
                tools,
                ['replay-supplement', '--in-fp', in_fp, '--out-fp', out_fp]
            )
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(zipfile.is_zipfile(out_fp))

            unzipped_path = os.path.join(tempdir, 'extracted')
            os.makedirs(unzipped_path)
            with zipfile.ZipFile(out_fp, 'r') as zfh:
                zfh.extractall(unzipped_path)

            self.assertEqual(os.listdir(unzipped_path), ['supplement'])

    def test_replay_supplement_cache(self):
        cache = Cache(os.path.join(self.tempdir, 'cache'))
        int_seq1 = Artifact.import_data('IntSequence1', [1, 2, 3])
        cache.save(int_seq1, 'int_seq1')
        cache_fp = os.path.join(self.tempdir, 'cache:int_seq1')

        self.runner.invoke(
            tools,
            ['replay-supplement', 'in-fp', cache_fp, '--out-fp', self.tempdir]
        )

    # Leave me alone I know the checksums don't match
    @pytest.mark.filterwarnings('ignore::UserWarning')
    def test_replay_param_not_found(self):
        rachis_cli = RootCommand()
        command = rachis_cli.get_command(ctx=None, name='dummy-plugin')

        in_fp = os.path.join(self.tempdir, 'concated_ints.qza')
        left_path = os.path.join(self.tempdir, 'left.qza')
        right_path = os.path.join(self.tempdir, 'right.qza')

        result = self.runner.invoke(
            command, ['split-ints', '--i-ints', in_fp,
                      '--o-left', left_path, '--o-right', right_path,
                      '--verbose'])

        self.assertEqual(result.exit_code, 0)

        left = Artifact.load(left_path)
        action_fp = os.path.join(
            left._archiver.provenance_dir, 'action', 'action.yaml'
        )
        with open(action_fp, 'r+') as action_fh:
            action_string = action_fh.read()
            action_yaml = yaml.safe_load(action_string)
            action_yaml['action']['parameters'].append({'not': 'real'})

            action_fh.write(yaml.dump(action_yaml))

        with tempfile.TemporaryDirectory() as tmpdir:
            out_fp = os.path.join(tmpdir, 'rendered.txt')
            result = self.runner.invoke(
                tools,
                ['replay-provenance', '--in-fp', left_path, '--out-fp',
                 out_fp, '--no-dump-recorded-metadata']
            )
            self.assertEqual(result.exit_code, 0)

            with open(out_fp, 'r') as fh:
                rendered = fh.read()

        MISSING_PARAM = \
"""
  # FIXME: The following parameter name was not found in your current
  # rachis environment. This may occur when the plugin version you have
  # installed does not match the version used in the original analysis.
  # Please see the docs and correct the parameter name before running.
  --?-not real \\
"""  # noqa: E128
        self.assertIn(MISSING_PARAM, rendered)

    def test_replay_action_not_found(self):
        datadir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'data'
        )
        artifact_fp = os.path.join(datadir, 'rarefied_table.qza')

        with tempfile.TemporaryDirectory() as tmpdir:
            out_fp = os.path.join(tmpdir, 'rendered.txt')
            result = self.runner.invoke(
                tools,
                ['replay-provenance', '--in-fp', artifact_fp, '--out-fp',
                 out_fp, '--no-dump-recorded-metadata']
            )
            self.assertEqual(result.exit_code, 0)

            with open(out_fp, 'r') as fh:
                rendered = fh.read()

        import1 = \
"""
rachis tools import \\
  --type 'Phylogeny[Rooted]' \\
  --input-path <your data here> \\
  --output-path phylogeny-rooted-0.qza
"""  # noqa: E128

        import2 = \
"""
rachis tools import \\
  --type 'FeatureTable[Frequency]' \\
  --input-path <your data here> \\
  --output-path feature-table-frequency-0.qza
"""  # noqa: E128

        self.assertIn(import1, rendered)
        self.assertIn(import2, rendered)

        FIXME_action = \
"""
# FIXME: The following action was not found in your current rachis
# environment. Please ensure the action and its parameters are correct before
# running.
rachis diversity core-metrics-phylogenetic \\
  --?-table feature-table-frequency-0.qza \\
  --?-phylogeny phylogeny-rooted-0.qza \\
  --?-sampling-depth 13 \\
  --?-metadata <your metadata filepath>.tsv \\
  --?-with-replacement False \\
  --?-n-jobs-or-threads 1 \\
  --?-ignore-missing-samples False \\
  --output-dir diversity-core-metrics-phylogenetic
"""  # noqa: E128
        self.assertIn(FIXME_action, rendered)


class TestAnnotations(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.tempdir = tempfile.mkdtemp(prefix='rachis-cli-test-temp-')

        # artifact without any starting annotations
        self.art1 = os.path.join(self.tempdir, 'ints1.qza')
        Artifact.import_data('IntSequence1', [0, 1, 2]).save(self.art1)

        # artifact that will have one starting annotation
        self.art2 = os.path.join(self.tempdir, 'ints2.qza')
        Artifact.import_data('IntSequence1', [1, 2, 3]).save(self.art2)

        # add note to art2
        self.note1 = Note(name='mynote', text='my special text')
        Artifact.load(self.art2).add_annotation(self.note1)

        # output path for self.art1 after adding annotation
        self.output1 = os.path.join(self.tempdir, 'ints1_annotated.qza')

        # annotation path for note from file
        self.note_file = os.path.join(
                self.tempdir, 'note_file.txt')
        with open(self.note_file, 'w') as f:
            f.write('my special text')

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    # ANNOTATION_CREATE
    def test_annotation_create_with_text_success(self):
        create_result = self.runner.invoke(
            tools,
            ['annotation-create', '--input-path', self.art1,
             '--annotation-type', 'Note',
             '--name', 'mynote', '--text', 'my special text',
             '--output-path', self.output1]
        )
        # confirm the command doesn't produce an error
        self.assertEqual(create_result.exit_code, 0)

        output_uuid = Result.load(self.output1).uuid
        # this will just produce one annotation
        for annotation in Result.load(self.output1).iter_annotations():
            annotation_uuid = annotation.id

        exp_namelist = {
            f'{output_uuid}/checksums.sha512',
            f'{output_uuid}/metadata.yaml',
            f'{output_uuid}/VERSION',
            f'{output_uuid}/annotations/{annotation_uuid}/checksums.sha512',
            f'{output_uuid}/annotations/{annotation_uuid}/metadata.yaml',
            f'{output_uuid}/annotations/{annotation_uuid}/note.txt',
            f'{output_uuid}/provenance/metadata.yaml',
            f'{output_uuid}/provenance/citations.bib',
            f'{output_uuid}/provenance/VERSION',
            f'{output_uuid}/provenance/conda-env.yaml',
            f'{output_uuid}/provenance/action/action.yaml',
            f'{output_uuid}/data/ints.txt'
        }

        exp_contents = 'my special text'

        with zipfile.ZipFile(self.output1, 'r') as zfh:
            # confirm file structure is what we expect
            self.assertEqual(exp_namelist, set(zfh.namelist()))

            annotation = zfh.read(
                f'{output_uuid}/annotations/{annotation_uuid}/note.txt'
            ).decode('utf-8')

            # confirm the annotation file contains the text we expect
            self.assertEqual(exp_contents, annotation)

    # make sure we see same results as w/inline text for input
    def test_annotation_create_with_file_success(self):
        create_result = self.runner.invoke(
            tools,
            ['annotation-create', '--input-path', self.art1,
             '--annotation-type', 'Note',
             '--name', 'mynote', '--file', self.note_file,
             '--output-path', self.output1]
        )
        # confirm the command doesn't produce an error
        self.assertEqual(create_result.exit_code, 0)

        output_uuid = Result.load(self.output1).uuid
        # this will just produce one annotation
        for annotation in Result.load(self.output1).iter_annotations():
            annotation_uuid = annotation.id

        exp_namelist = {
            f'{output_uuid}/checksums.sha512',
            f'{output_uuid}/metadata.yaml',
            f'{output_uuid}/VERSION',
            f'{output_uuid}/annotations/{annotation_uuid}/checksums.sha512',
            f'{output_uuid}/annotations/{annotation_uuid}/metadata.yaml',
            f'{output_uuid}/annotations/{annotation_uuid}/note.txt',
            f'{output_uuid}/provenance/metadata.yaml',
            f'{output_uuid}/provenance/citations.bib',
            f'{output_uuid}/provenance/VERSION',
            f'{output_uuid}/provenance/conda-env.yaml',
            f'{output_uuid}/provenance/action/action.yaml',
            f'{output_uuid}/data/ints.txt'
        }

        exp_contents = 'my special text'

        with zipfile.ZipFile(self.output1, 'r') as zfh:
            # confirm file structure is what we expect
            self.assertEqual(exp_namelist, set(zfh.namelist()))

            annotation = zfh.read(
                f'{output_uuid}/annotations/{annotation_uuid}/note.txt'
            ).decode('utf-8')

            # confirm the annotation file contains the text we expect
            self.assertEqual(exp_contents, annotation)

    # make sure we don't run into any errors & see same result
    # when overwriting the original artifact fp
    def test_annotation_create_overwriting_input_file_success(self):
        create_result = self.runner.invoke(
            tools,
            ['annotation-create', '--input-path', self.art1,
             '--annotation-type', 'Note',
             '--name', 'mynote', '--text', 'my special text',
             '--output-path', self.art1]
        )
        # confirm the command doesn't produce an error
        self.assertEqual(create_result.exit_code, 0)

        output_uuid = Result.load(self.art1).uuid
        # this will just produce one annotation
        for annotation in Result.load(self.art1).iter_annotations():
            annotation_uuid = annotation.id

        exp_namelist = {
            f'{output_uuid}/checksums.sha512',
            f'{output_uuid}/metadata.yaml',
            f'{output_uuid}/VERSION',
            f'{output_uuid}/annotations/{annotation_uuid}/checksums.sha512',
            f'{output_uuid}/annotations/{annotation_uuid}/metadata.yaml',
            f'{output_uuid}/annotations/{annotation_uuid}/note.txt',
            f'{output_uuid}/provenance/metadata.yaml',
            f'{output_uuid}/provenance/citations.bib',
            f'{output_uuid}/provenance/VERSION',
            f'{output_uuid}/provenance/conda-env.yaml',
            f'{output_uuid}/provenance/action/action.yaml',
            f'{output_uuid}/data/ints.txt'
        }

        exp_contents = 'my special text'

        with zipfile.ZipFile(self.art1, 'r') as zfh:
            # confirm file structure is what we expect
            self.assertEqual(exp_namelist, set(zfh.namelist()))

            annotation = zfh.read(
                f'{output_uuid}/annotations/{annotation_uuid}/note.txt'
            ).decode('utf-8')

            # confirm the annotation file contains the text we expect
            self.assertEqual(exp_contents, annotation)

    def test_annotation_create_invalid_annotation_type_failure(self):
        create_result = self.runner.invoke(
            tools,
            ['annotation-create', '--input-path', self.art1,
             '--annotation-type', 'Foo',
             '--name', 'mynote', '--text', 'my special text',
             '--output-path', self.output1]
        )
        # confirm the command does produce an error
        self.assertEqual(create_result.exit_code, 1)
        self.assertIn("Invalid value for '--annotation-type': 'Foo'",
                      create_result.output)

    def test_annotation_create_text_and_filepath_provided_failure(self):
        create_result = self.runner.invoke(
            tools,
            ['annotation-create', '--input-path', self.art1,
             '--annotation-type', 'Note',
             '--name', 'mynote', '--text', 'my special text',
             '--file', self.note_file, '--output-path', self.output1]
        )
        # confirm the command does produce an error
        self.assertEqual(create_result.exit_code, 2)
        self.assertIn("Exactly one of `--text` or `--file` must be provided",
                      create_result.output)

    def test_annotation_create_no_text_or_filepath_provided_failure(self):
        create_result = self.runner.invoke(
            tools,
            ['annotation-create', '--input-path', self.art1,
             '--annotation-type', 'Note',
             '--name', 'mynote', '--output-path', self.output1]
        )
        # confirm the command does produce an error
        self.assertEqual(create_result.exit_code, 2)
        self.assertIn("Exactly one of `--text` or `--file` must be provided",
                      create_result.output)

    def test_annotation_create_invalid_annotation_name_failure(self):
        create_result = self.runner.invoke(
            tools,
            ['annotation-create', '--input-path', self.art1,
             '--annotation-type', 'Note',
             '--name', '@#$%^&*', '--text', 'my special text',
             '--output-path', self.output1]
        )
        # confirm the command does produce an error
        self.assertEqual(create_result.exit_code, 1)
        self.assertIn('Name "@#$%^&*" is not a valid Python identifier',
                      str(create_result.exception))

    def test_annotation_create_existing_annotation_name_failure(self):
        create_result = self.runner.invoke(
            tools,
            ['annotation-create', '--input-path', self.art2,
             '--annotation-type', 'Note',
             '--name', 'mynote', '--file', self.note_file,
             '--output-path', self.output1]
        )
        # confirm the command does produce an error
        self.assertEqual(create_result.exit_code, 1)
        self.assertIn('Duplicate name detected when attempting to add '
                      'Annotation with name: "mynote"', create_result.output)

    # ANNOTATION_REMOVE
    def test_annotation_remove_new_filepath_success(self):
        remove_result = self.runner.invoke(
            tools,
            ['annotation-remove', '--input-path', self.art2,
             '--name', 'mynote', '--output-path', self.output1]
        )
        # confirm the command doesn't produce an error
        self.assertEqual(remove_result.exit_code, 0)

        with zipfile.ZipFile(self.output1, 'r') as zfh:
            # confirm annotations dir has been removed
            self.assertNotIn('annotations', set(zfh.namelist()))

    def test_annotation_remove_existing_filepath_success(self):
        remove_result = self.runner.invoke(
            tools,
            ['annotation-remove', '--input-path', self.art2,
             '--name', 'mynote', '--output-path', self.art2]
        )
        # confirm the command doesn't produce an error
        self.assertEqual(remove_result.exit_code, 0)

        with zipfile.ZipFile(self.art2, 'r') as zfh:
            # confirm annotations dir has been removed
            self.assertNotIn('annotations', set(zfh.namelist()))

    def test_annotation_remove_no_annotations_failure(self):
        remove_result = self.runner.invoke(
            tools,
            ['annotation-remove', '--input-path', self.art1,
             '--name', 'mynote', '--output-path', self.output1]
        )
        # confirm the command does produce an error
        self.assertEqual(remove_result.exit_code, 1)
        self.assertIn('No Annotation found with name: "mynote"',
                      remove_result.output)

    def test_annotation_remove_wrong_annotation_name_failure(self):
        remove_result = self.runner.invoke(
            tools,
            ['annotation-remove', '--input-path', self.art2,
             '--name', 'myspecialnote', '--output-path', self.output1]
        )
        # confirm the command does produce an error
        self.assertEqual(remove_result.exit_code, 1)
        self.assertIn('No Annotation found with name: "myspecialnote"',
                      remove_result.output)

    # ANNOTATION_FETCH
    def test_annotation_fetch_no_verbose_success(self):
        fetch_result = self.runner.invoke(
            tools,
            ['annotation-fetch', '--input-path', self.art2, '--name', 'mynote']
        )
        # confirm the command doesn't produce an error
        self.assertEqual(fetch_result.exit_code, 0)
        # ensure the annotation type & name we expect is present in the output
        self.assertRegex(fetch_result.output,
                         r'name:\s*mynote\s*type:\s*Note\b')

    def test_annotation_fetch_verbose_success(self):
        fetch_result = self.runner.invoke(
            tools,
            ['annotation-fetch', '--input-path', self.art2,
             '--name', 'mynote', '--verbose']
        )
        # confirm the command doesn't produce an error
        self.assertEqual(fetch_result.exit_code, 0)
        # ensure the annotation type & name we expect is present in the output
        self.assertRegex(
            fetch_result.output,
            r'name:\s*mynote\s*type:\s*Note\s*contents:\s*my special text\b'
        )

    def test_annotation_fetch_wrong_name_failure(self):
        fetch_result = self.runner.invoke(
            tools,
            ['annotation-fetch', '--input-path', self.art2,
             '--name', 'mynote2']
        )
        # confirm the command does produce an error
        self.assertEqual(fetch_result.exit_code, 1)
        self.assertIn('No Annotation with name: "mynote2"',
                      fetch_result.output)

    # ANNOTATION_LIST
    def test_annotation_list_multiple_annotations_success(self):
        self.note2 = Note(name='myothernote', text='my extra special text')

        self.arty = Artifact.load(self.art2)
        self.arty.add_annotation(self.note2)
        self.arty.save(self.art2)

        list_result = self.runner.invoke(
            tools,
            ['annotation-list', '--input-path', self.art2]
        )
        # confirm the command doesn't produce an error
        self.assertEqual(list_result.exit_code, 0)
        self.assertRegex(list_result.output,
                         r'name:\s*mynote\s*type:\s*Note\b')
        self.assertRegex(list_result.output,
                         r'name:\s*myothernote\s*type:\s*Note\b')

    def test_annotation_list_no_annotations_failure(self):
        list_result = self.runner.invoke(
            tools,
            ['annotation-list', '--input-path', self.art1]
        )
        # confirm the command does produce an error
        self.assertEqual(list_result.exit_code, 1)
        self.assertIn('No Annotations found.', list_result.output)


class TestCacheExport(unittest.TestCase):
    def setUp(self):
        dummy_plugin = get_dummy_plugin()

        self.runner = CliRunner()
        self.tempdir = tempfile.mkdtemp(prefix='rachis-cli-test-temp-')
        self.cache = Cache(os.path.join(self.tempdir, 'cache'))

        ints1 = Artifact.import_data(
            'IntSequence1', [0, 42, 43], list)
        self.ints1 = self.cache.save(ints1, 'ints1')

        most_common_viz = dummy_plugin.actions['most_common_viz']
        viz = most_common_viz(ints1).visualization
        self.viz = self.cache.save(viz, 'viz')

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_cache_export_to_dir_w_format(self):
        output_path = os.path.join(self.tempdir, 'output')
        result = self.runner.invoke(tools, [
            'cache-export', '--cache', str(self.cache.path), '--key', 'ints1',
            '--output-path', output_path, '--output-format',
            'IntSequenceDirectoryFormat'
        ])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(os.path.isdir(output_path))

    def test_cache_export_to_dir_no_format(self):
        output_path = os.path.join(self.tempdir, 'output')
        self.runner.invoke(tools, [
            'cache-export', '--cache', str(self.cache.path), '--key', 'viz',
            '--output-path', output_path
        ])

        self.assertTrue(os.path.isdir(output_path))
        self.assertIn('index.html', os.listdir(output_path))
        self.assertIn('index.tsv', os.listdir(output_path))

    def test_cache_export_to_file(self):
        output_path = os.path.join(self.tempdir, 'output')
        result = self.runner.invoke(tools, [
            'cache-export', '--cache', str(self.cache.path), '--key', 'ints1',
            '--output-path', output_path, '--output-format',
            'IntSequenceFormatV2'
            ])

        with open(output_path, 'r') as f:
            file = f.read()
        self.assertEqual(result.exit_code, 0)
        self.assertIn('0', file)
        self.assertIn('42', file)
        self.assertIn('43', file)

    def test_cache_export_to_file_creates_directories(self):
        output_path = os.path.join(self.tempdir, 'somewhere', 'output')
        result = self.runner.invoke(tools, [
            'cache-export', '--cache', str(self.cache.path), '--key', 'ints1',
            '--output-path', output_path, '--output-format',
            'IntSequenceFormatV2'
            ])

        with open(output_path, 'r') as f:
            file = f.read()
        self.assertEqual(result.exit_code, 0)
        self.assertIn('0', file)
        self.assertIn('42', file)
        self.assertIn('43', file)

    def test_cache_export_visualization_to_dir(self):
        output_path = os.path.join(self.tempdir, 'output')
        self.runner.invoke(tools, [
            'cache-export', '--cache', str(self.cache.path), '--key', 'viz',
            '--output-path', output_path
        ])

        self.assertIn('index.html', os.listdir(output_path))
        self.assertIn('index.tsv', os.listdir(output_path))
        self.assertTrue(os.path.isdir(output_path))

    def test_cache_export_visualization_w_format(self):
        output_path = os.path.join(self.tempdir, 'output')
        result = self.runner.invoke(tools, [
            'cache-export', '--cache', str(self.cache.path), '--key', 'viz',
            '--output-path', output_path, '--output-format',
            'IntSequenceDirectoryFormat'
        ])

        self.assertEqual(result.exit_code, 1)
        self.assertIn('visualization', result.output)
        self.assertIn('--output-format', result.output)

    def test_cache_export_path_file_is_replaced(self):
        output_path = os.path.join(self.tempdir, 'output')
        with open(output_path, 'w') as file:
            file.write('HelloWorld')
        self.runner.invoke(tools, [
            'cache-export', '--cache', str(self.cache.path), '--key', 'ints1',
            '--output-path', output_path, '--output-format',
            'IntSequenceFormatV2'
        ])

        with open(output_path, 'r') as f:
            file = f.read()
        self.assertNotIn('HelloWorld', file)

    def test_cache_export_to_file_with_format_success_message(self):
        output_path = os.path.join(self.tempdir, 'output.int')
        result = self.runner.invoke(tools, [
            'cache-export', '--cache', str(self.cache.path), '--key', 'ints1',
            '--output-path', output_path, '--output-format',
            'IntSequenceFormatV2'
            ])
        success = f'Exported {self.cache.path}:ints1 as IntSequenceFormatV2 ' \
                  f'to file {output_path}\n'
        self.assertEqual(success, result.output)

    def test_cache_export_to_dir_without_format_success_message(self):
        output_path = os.path.join(self.tempdir, 'output')
        result = self.runner.invoke(tools, [
            'cache-export', '--cache', str(self.cache.path), '--key', 'ints1',
            '--output-path', output_path
            ])
        success = f'Exported {self.cache.path}:ints1 as ' \
                  f'IntSequenceDirectoryFormat to directory {output_path}\n'
        self.assertEqual(success, result.output)

    def test_cache_export_visualization_to_dir_success_message(self):
        output_path = os.path.join(self.tempdir, 'output')
        result = self.runner.invoke(tools, [
            'cache-export', '--cache', str(self.cache.path), '--key', 'viz',
            '--output-path', output_path
        ])
        success = f'Exported {self.cache.path}:viz as Visualization to ' \
                  f'directory {output_path}\n'
        self.assertEqual(success, result.output)

    def test_cache_export_bad_cache(self):
        output_path = os.path.join(self.tempdir, 'output')
        result = self.runner.invoke(tools, [
            'cache-export', '--cache', str(self.tempdir), '--key', 'viz',
            '--output-path', output_path
        ])

        failure = f"Path: '{self.tempdir}' already exists and is not a cache."
        self.assertIn(failure, result.output)

    def test_cache_export_bad_key(self):
        output_path = os.path.join(self.tempdir, 'output')
        result = self.runner.invoke(tools, [
            'cache-export', '--cache', str(self.cache.path), '--key', 'bad',
            '--output-path', output_path
        ])

        failure = f"The cache '{self.cache.path}' does not contain the key " \
                  "'bad'"
        self.assertIn(failure, result.output)


class TestCacheExportToFileFormat(unittest.TestCase):
    def setUp(self):
        dummy_plugin = get_dummy_plugin()

        self.runner = CliRunner()
        self.tempdir = tempfile.mkdtemp(prefix='rachis-cli-test-temp-')
        self.cache = Cache(os.path.join(self.tempdir, 'cache'))

        ints1 = Artifact.import_data(
            'IntSequence1', [0, 42, 43], list)
        self.ints1 = self.cache.save(ints1, 'ints1')

        most_common_viz = dummy_plugin.actions['most_common_viz']
        viz = most_common_viz(ints1).visualization
        self.viz = self.cache.save(viz, 'viz')

        # Working directory is changed to temp directory to prevent cluttering
        # the repo directory with test files
        self.current_dir = os.getcwd()
        os.chdir(self.tempdir)

    def tearDown(self):
        shutil.rmtree(self.tempdir)
        os.chdir(self.current_dir)

    def test_cache_export_file_format(self):
        output_path = os.path.join(os.getcwd(), 'output')
        result = self.runner.invoke(tools, [
            'cache-export', '--cache', str(self.cache.path), '--key', 'ints1',
            '--output-path', output_path, '--output-format',
            'IntSequenceFormat'
        ])

        success = f'Exported {self.cache.path}:ints1 as IntSequenceFormat ' \
                  f'to file {output_path}\n'
        self.assertEqual(success, result.output)

    def test_cache_export_to_filename_without_path(self):
        output_path = 'output'
        result = self.runner.invoke(tools, [
            'cache-export', '--cache', str(self.cache.path), '--key', 'viz',
            '--output-path', output_path
        ])
        success = f'Exported {self.cache.path}:viz as Visualization to ' \
                  f'directory {output_path}\n'
        self.assertEqual(success, result.output)

    def test_cache_export_dir_format(self):
        result = self.runner.invoke(tools, [
            'cache-export', '--cache', str(str(self.cache.path)), '--key',
            'ints1', '--output-path', os.getcwd(), '--output-format',
            'IntSequenceDirectoryFormat'
        ])

        success = f'Exported {self.cache.path}:ints1 as ' \
                  f'IntSequenceDirectoryFormat to directory {os.getcwd()}\n'
        self.assertEqual(success, result.output)

    def test_cache_export_dir_format_nested(self):
        output_path = os.path.join(os.getcwd(), 'output')
        result = self.runner.invoke(tools, [
            'cache-export', '--cache', str(self.cache.path), '--key', 'ints1',
            '--output-path', output_path, '--output-format',
            'IntSequenceDirectoryFormat'
        ])

        success = f'Exported {self.cache.path}:ints1 as ' \
                  f'IntSequenceDirectoryFormat to directory {output_path}\n'
        self.assertEqual(success, result.output)


class TestMakeReport(unittest.TestCase):
    def setUp(self):
        # ensure dummy plugin is registered
        self.dp = get_dummy_plugin()
        self.runner = CliRunner()
        self.tempdir = tempfile.mkdtemp(prefix='rachis-cli-test-temp-')

        # create an artifact to drive visualizations
        self.ints = Artifact.import_data('IntSequence1', [0, 1, 2])

        # create two visualizations with unique basenames
        self.viz1 = os.path.join(self.tempdir, 'viz1.qzv')
        self.dp.actions['most_common_viz'](self.ints).visualization.save(
            self.viz1)

        self.viz2 = os.path.join(self.tempdir, 'viz2.qzv')
        self.dp.actions['most_common_viz'](self.ints).visualization.save(
            self.viz2)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_make_report_success(self):
        report = os.path.join(self.tempdir, 'report.qzv')
        result = self.runner.invoke(
            tools, ['make-report', self.viz1, self.viz2, '--report-path',
                    report])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('Report saved to', result.output)
        # ensure the report file was written and is a zip archive
        self.assertTrue(zipfile.is_zipfile(report))

    def test_make_report_duplicate_names(self):
        # create two visualizations that share the same filename but live in
        # different directories to trigger the duplicate-name error
        a_dir = os.path.join(self.tempdir, 'a')
        b_dir = os.path.join(self.tempdir, 'b')
        os.mkdir(a_dir)
        os.mkdir(b_dir)

        dup1 = os.path.join(a_dir, 'viz.qzv')
        dup2 = os.path.join(b_dir, 'viz.qzv')
        self.dp.actions['most_common_viz'](self.ints).visualization.save(dup1)
        self.dp.actions['most_common_viz'](self.ints).visualization.save(dup2)

        report = os.path.join(self.tempdir, 'report.qzv')
        result = self.runner.invoke(
            tools, ['make-report', dup1, dup2, '--report-path', report])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('Multiple files share the same name', result.output)


class TestRedactMetadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.mkdtemp(prefix='rachis-cli-test-temp-')

        metadata_path = os.path.join(cls.tempdir, 'metadata.tsv')
        with open(metadata_path, 'w') as fh:
            fh.write('sample-id\tbarcode-sequence\n')
            fh.write('1\tACT')
        dummy_md = Metadata.load(metadata_path)

        pm = PluginManager()
        identity_with_metadata = pm.plugins['dummy-plugin'].actions[
            'identity_with_metadata'
        ]

        cls.artifact1_fp = os.path.join(cls.tempdir, 'a1.qza')
        cls.artifact2_fp = os.path.join(cls.tempdir, 'a2.qza')
        cls.artifact3_fp = os.path.join(cls.tempdir, 'a3.qza')

        artifact1 = Artifact.import_data(IntSequence1, [0, 6, 7])
        artifact1, = identity_with_metadata(artifact1, dummy_md)
        artifact1.save(cls.artifact1_fp)
        artifact2 = Artifact.import_data(IntSequence2, [3, 4, 5])
        artifact2, = identity_with_metadata(artifact2, dummy_md)
        artifact2.save(cls.artifact2_fp)
        artifact3 = Artifact.import_data(SingleInt, 9)
        artifact3.save(cls.artifact3_fp)

        cls.runner = CliRunner()
        cls.redacted_fp = os.path.join(cls.tempdir, 'redacted')

    def test_with_metadata(self):
        redacted_fp = self.redacted_fp + '.qza'
        result = self.runner.invoke(tools, [
            'redact-metadata', '--input-path', self.artifact1_fp,
            '--output-path', redacted_fp
        ])

        self.assertEqual(result.exit_code, 0)
        success = f'Succesfully redacted metadata from {self.artifact1_fp}, ' \
                  f'and saved to {redacted_fp}.\n'
        self.assertEqual(success, result.output)

    def test_fails_already_redacted(self):
        '''
        Redacting metadata from an Artifact twice should fail.
        '''
        redacted_fp = self.redacted_fp + '.qza'
        self.runner.invoke(tools, [
            'redact-metadata', '--input-path', self.artifact2_fp,
            '--output-path', redacted_fp
        ])

        result = self.runner.invoke(tools, [
            'redact-metadata', '--input-path', redacted_fp,
            '--output-path', os.path.join(self.tempdir, 'bad')
        ])

        self.assertEqual(result.exit_code, 1)
        self.assertIn('only redacted metadata', result.output)

    def test_fails_no_metadata(self):
        '''
        Redacting metadata from an Artifact with no metadata should fail.
        '''
        redacted_fp = self.redacted_fp + '.qza'
        result = self.runner.invoke(tools, [
            'redact-metadata', '--input-path', self.artifact3_fp,
            '--output-path', redacted_fp
        ])

        self.assertEqual(result.exit_code, 1)
        self.assertIn('Result without metadata', result.output)


if __name__ == "__main__":
    unittest.main()
