# ----------------------------------------------------------------------------
# Copyright (c) 2016-2022, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import os
import gc
import shutil
import unittest
import tempfile

from click.testing import CliRunner
from qiime2 import Artifact
from qiime2.core.testing.util import get_dummy_plugin
from qiime2.metadata.base import SUPPORTED_COLUMN_TYPES
from qiime2.core.cache import Cache

from q2cli.builtin.tools import tools, _load_metadata
from q2cli.commands import RootCommand


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
        casted_metadata = _load_metadata(self.output_file)
        self.assertNotIn('extra', casted_metadata.columns.keys())

    def test_complete_successful_run(self):
        result = self.runner.invoke(
            tools, ['cast-metadata', self.metadata_file, '--cast',
                    'numbers:categorical', '--output-file', self.output_file])

        self.assertEqual(result.exit_code, 0)
        input_metadata = _load_metadata(self.metadata_file)
        self.assertEqual('numeric', input_metadata.columns['numbers'].type)

        casted_metadata = _load_metadata(self.output_file)
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
        self.cache = Cache(os.path.join(self.tempdir.name, 'new_cache'))

    def tearDown(self):
        self.tempdir.cleanup()

    def test_cache_create(self):
        cache_path = os.path.join(self.tempdir.name, 'created_cache')

        result = self.runner.invoke(
            tools, ['cache-create', '--path', cache_path])

        success = "Created cache at '%s'\n" % cache_path
        self.assertEqual(success, result.output)
        self.assertTrue(Cache.is_cache(cache_path))

    def test_cache_remove(self):
        cache_path = os.path.join(self.tempdir.name, 'remove_cache')
        Cache(cache_path)
        self.assertTrue(Cache.is_cache(cache_path))

        result = self.runner.invoke(
            tools, ['cache-remove', '--path', cache_path])

        success = "Removed cache at '%s'\n" % cache_path
        self.assertEqual(success, result.output)
        self.assertFalse(os.path.exists(cache_path))

    def test_cache_garbage_collection(self):
        # Data referenced directly by key
        self.cache.save(self.art1, 'foo')
        # Data referenced by pool that is referenced by key
        pool = self.cache.create_pool(['bar'])
        pool.save(self.art2)
        # We will be manually deleting the keys that back these two
        self.cache.save(self.art3, 'baz')
        pool = self.cache.create_pool(['qux'])
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
            ['cache-garbage-collection', '--path', str(self.cache.path)])

        success = "Ran garbage collection on cache at '%s'\n" % self.cache.path
        self.assertEqual(success, result.output)

        # Assert cache looks how we want post gc
        post_gc_contents = _get_cache_contents(self.cache)
        self.assertEqual(expected_post_gc_contents, post_gc_contents)

    def test_cache_save(self):
        artifact = os.path.join(self.tempdir.name, 'artifact.qza')
        self.art1.save(artifact)

        result = self.runner.invoke(
            tools, ['cache-save', '--cache-path', str(self.cache.path),
                    '--artifact-path', artifact, '--key', 'key'])

        success = "Saved the artifact '%s' to the cache '%s' under the key " \
            "'key'\n" % (artifact, self.cache.path)
        self.assertEqual(success, result.output)

    def test_cache_load(self):
        artifact = os.path.join(self.tempdir.name, 'artifact.qza')
        self.cache.save(self.art1, 'key')

        result = self.runner.invoke(
            tools, ['cache-load', '--cache-path', str(self.cache.path),
                    '--key', 'key', '--output-path', artifact])

        success = "Loaded artifact with the key 'key' from the cache '%s' " \
            "and saved it to the file '%s'\n" % (self.cache.path, artifact)
        self.assertEqual(success, result.output)

    def test_cache_roundtrip(self):
        in_artifact = os.path.join(self.tempdir.name, 'in_artifact.qza')
        out_artifact = os.path.join(self.tempdir.name, 'out_artifact.qza')

        self.art1.save(in_artifact)

        result = self.runner.invoke(
            tools, ['cache-save', '--cache-path', str(self.cache.path),
                    '--artifact-path', in_artifact, '--key', 'key'])

        success = "Saved the artifact '%s' to the cache '%s' under the key " \
            "'key'\n" % (in_artifact, self.cache.path)
        self.assertEqual(success, result.output)

        result = self.runner.invoke(
            tools, ['cache-load', '--cache-path', str(self.cache.path),
                    '--key', 'key', '--output-path', out_artifact])

        success = "Loaded artifact with the key 'key' from the cache '%s' " \
            "and saved it to the file '%s'\n" % (self.cache.path, out_artifact)
        self.assertEqual(success, result.output)

        artifact = Artifact.load(out_artifact)
        self.assertEqual([0, 1, 2], artifact.view(list))


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


if __name__ == "__main__":
    unittest.main()
