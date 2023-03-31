# ----------------------------------------------------------------------------
# Copyright (c) 2016-2022, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import shutil
import os.path
import unittest
import unittest.mock
import tempfile

from click.testing import CliRunner
from qiime2 import Artifact
from qiime2.core.testing.type import (IntSequence1, IntSequence2, Mapping,
                                      SingleInt)
from qiime2.core.testing.util import get_dummy_plugin
from qiime2.core.cache import Cache

from q2cli.commands import RootCommand
from q2cli.builtin.tools import tools


class TestCacheCli(unittest.TestCase):
    def setUp(self):
        get_dummy_plugin()

        self.runner = CliRunner()
        self.plugin_command = RootCommand().get_command(
            ctx=None, name='dummy-plugin')
        self.tempdir = tempfile.mkdtemp(prefix='qiime2-q2cli-test-temp-')
        self.cache = Cache(os.path.join(self.tempdir, 'new_cache'))

        self.art1 = Artifact.import_data(IntSequence1, [0, 1, 2])
        self.art2 = Artifact.import_data(IntSequence1, [3, 4, 5])
        self.art3 = Artifact.import_data(IntSequence2, [6, 7, 8])
        self.art4 = Artifact.import_data(SingleInt, 0)
        self.art5 = Artifact.import_data(SingleInt, 1)
        self.mapping = Artifact.import_data(Mapping, {'a': '1', 'b': '2'})

        self.non_cache_output = os.path.join(self.tempdir, 'output.qza')
        self.art3_non_cache = os.path.join(self.tempdir, 'art3.qza')

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _run_command(self, *args):
        return self.runner.invoke(self.plugin_command, args)

    def test_inputs_from_cache(self):
        self.cache.save(self.art1, 'art1')
        self.cache.save(self.art2, 'art2')
        self.cache.save(self.art3, 'art3')

        art1_path = str(self.cache.path) + ':art1'
        art2_path = str(self.cache.path) + ':art2'
        art3_path = str(self.cache.path) + ':art3'

        result = self._run_command(
            'concatenate-ints', '--i-ints1', art1_path, '--i-ints2', art2_path,
            '--i-ints3', art3_path, '--p-int1', '9', '--p-int2', '10',
            '--o-concatenated-ints', self.non_cache_output, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(Artifact.load(self.non_cache_output).view(list),
                         [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

    def test_inputs_split(self):
        self.cache.save(self.art1, 'art1')
        self.cache.save(self.art2, 'art2')
        self.art3.save(self.art3_non_cache)

        art1_path = str(self.cache.path) + ':art1'
        art2_path = str(self.cache.path) + ':art2'

        result = self._run_command(
            'concatenate-ints', '--i-ints1', art1_path, '--i-ints2', art2_path,
            '--i-ints3', self.art3_non_cache, '--p-int1', '9', '--p-int2',
            '10', '--o-concatenated-ints', self.non_cache_output, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(Artifact.load(self.non_cache_output).view(list),
                         [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

    def test_colon_in_input_path_not_cache(self):
        art_path = os.path.join(self.tempdir, 'art:1.qza')
        self.art1.save(art_path)

        left_path = os.path.join(self.tempdir, 'left.qza')
        right_path = os.path.join(self.tempdir, 'right.qza')

        result = self._run_command(
            'split-ints', '--i-ints', art_path, '--o-left', left_path,
            '--o-right', right_path, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(Artifact.load(left_path).view(list), [0])
        self.assertEqual(Artifact.load(right_path).view(list), [1, 2])

    def test_colon_in_cache_path(self):
        cache = Cache(os.path.join(self.tempdir, 'new:cache'))
        cache.save(self.art1, 'art')

        art_path = str(cache.path) + ':art'

        left_path = os.path.join(self.tempdir, 'left.qza')
        right_path = os.path.join(self.tempdir, 'right.qza')

        result = self._run_command(
            'split-ints', '--i-ints', art_path, '--o-left', left_path,
            '--o-right', right_path, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(Artifact.load(left_path).view(list), [0])
        self.assertEqual(Artifact.load(right_path).view(list), [1, 2])

    def test_output_to_cache(self):
        self.cache.save(self.art1, 'art1')
        self.cache.save(self.art2, 'art2')
        self.cache.save(self.art3, 'art3')

        art1_path = str(self.cache.path) + ':art1'
        art2_path = str(self.cache.path) + ':art2'
        art3_path = str(self.cache.path) + ':art3'

        out_path = str(self.cache.path) + ':out'

        result = self._run_command(
            'concatenate-ints', '--i-ints1', art1_path, '--i-ints2', art2_path,
            '--i-ints3', art3_path, '--p-int1', '9', '--p-int2', '10',
            '--o-concatenated-ints', out_path, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(self.cache.load('out').view(list),
                         [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

    def test_outputs_to_cache(self):
        self.cache.save(self.art1, 'art1')
        art1_path = str(self.cache.path) + ':art1'

        left_path = str(self.cache.path) + ':left'
        right_path = str(self.cache.path) + ':right'

        result = self._run_command(
            'split-ints', '--i-ints', art1_path, '--o-left', left_path,
            '--o-right', right_path, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(self.cache.load('left').view(list), [0])
        self.assertEqual(self.cache.load('right').view(list), [1, 2])

    def test_outputs_split(self):
        self.cache.save(self.art1, 'art1')
        art1_path = str(self.cache.path) + ':art1'

        left_path = str(self.cache.path) + ':left'

        result = self._run_command(
            'split-ints', '--i-ints', art1_path, '--o-left', left_path,
            '--o-right', self.non_cache_output, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(self.cache.load('left').view(list), [0])
        self.assertEqual(Artifact.load(self.non_cache_output).view(list),
                         [1, 2])

    def test_invalid_cache_path_input(self):
        art1_path = 'not_a_cache:art1'

        left_path = str(self.cache.path) + ':left'
        right_path = str(self.cache.path) + ':right'

        result = self._run_command(
            'split-ints', '--i-ints', art1_path, '--o-left', left_path,
            '--o-right', right_path, '--verbose'
        )

        self.assertEqual(result.exit_code, 1)
        self.assertRegex(result.output, r"cache")

    def test_invalid_cache_path_output(self):
        self.cache.save(self.art1, 'art1')
        art1_path = str(self.cache.path) + ':art1'

        left_path = '/this/is/not_a_cache:left'
        right_path = str(self.cache.path) + ':right'

        result = self._run_command(
            'split-ints', '--i-ints', art1_path, '--o-left', left_path,
            '--o-right', right_path, '--verbose'
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn('does not exist', result.output)

    def test_colon_in_out_path_not_cache(self):
        self.cache.save(self.art1, 'art1')
        self.cache.save(self.art2, 'art2')
        self.cache.save(self.art3, 'art3')

        art1_path = str(self.cache.path) + ':art1'
        art2_path = str(self.cache.path) + ':art2'
        art3_path = str(self.cache.path) + ':art3'

        out_path = os.path.join(self.tempdir, 'out:put.qza')

        result = self._run_command(
            'concatenate-ints', '--i-ints1', art1_path, '--i-ints2', art2_path,
            '--i-ints3', art3_path, '--p-int1', '9', '--p-int2', '10',
            '--o-concatenated-ints', out_path, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(Artifact.load(out_path).view(list),
                         [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

    def test_collection_roundtrip_list(self):
        key1 = 'out1'
        key2 = 'out2'

        collection_out1 = str(self.cache.path) + ':' + key1
        collection_out2 = str(self.cache.path) + ':' + key2

        result = self._run_command(
            'list-params', '--p-ints', '0', '--p-ints', '1', '--o-output',
            collection_out1, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = self.cache.load_collection(key1)
        loaded_key = self.cache.read_key(key1)

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)

        self.assertEqual(loaded_key['order'],
                         [{'0': str(collection['0'].uuid)},
                          {'1': str(collection['1'].uuid)}])

        result = self._run_command(
            'list-of-ints', '--i-ints', collection_out1, '--o-output',
            collection_out2, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = self.cache.load_collection(key2)
        loaded_key = self.cache.read_key(key2)

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)

        self.assertEqual(loaded_key['order'],
                         [{'0': str(collection['0'].uuid)},
                          {'1': str(collection['1'].uuid)}])

    def test_collection_roundtrip_dict_keyed(self):
        key1 = 'out1'
        key2 = 'out2'

        collection_out1 = str(self.cache.path) + ':' + key1
        collection_out2 = str(self.cache.path) + ':' + key2

        result = self._run_command(
            'dict-params', '--p-ints', 'foo:0', '--p-ints', 'bar:1',
            '--o-output', collection_out1, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = self.cache.load_collection(key1)
        loaded_key = self.cache.read_key(key1)

        self.assertEqual(collection['foo'].view(int), 0)
        self.assertEqual(collection['bar'].view(int), 1)

        self.assertEqual(loaded_key['order'],
                         [{'foo': str(collection['foo'].uuid)},
                          {'bar': str(collection['bar'].uuid)}])

        result = self._run_command(
            'dict-of-ints', '--i-ints', collection_out1, '--o-output',
            collection_out2, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = self.cache.load_collection(key2)
        loaded_key = self.cache.read_key(key2)

        self.assertEqual(collection['foo'].view(int), 0)
        self.assertEqual(collection['bar'].view(int), 1)

        self.assertEqual(loaded_key['order'],
                         [{'foo': str(collection['foo'].uuid)},
                          {'bar': str(collection['bar'].uuid)}])

    def test_collection_roundtrip_dict_unkeyed(self):
        key1 = 'out1'
        key2 = 'out2'

        collection_out1 = str(self.cache.path) + ':' + key1
        collection_out2 = str(self.cache.path) + ':' + key2

        result = self._run_command(
            'dict-params', '--p-ints', '0', '--p-ints', '1',
            '--o-output', collection_out1, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = self.cache.load_collection(key1)
        loaded_key = self.cache.read_key(key1)

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)

        self.assertEqual(loaded_key['order'],
                         [{'0': str(collection['0'].uuid)},
                          {'1': str(collection['1'].uuid)}])

        result = self._run_command(
            'dict-of-ints', '--i-ints', collection_out1, '--o-output',
            collection_out2, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = self.cache.load_collection(key2)
        loaded_key = self.cache.read_key(key2)

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)

        self.assertEqual(loaded_key['order'],
                         [{'0': str(collection['0'].uuid)},
                          {'1': str(collection['1'].uuid)}])

    def test_de_facto_list(self):
        self.cache.save(self.art4, 'art4')
        self.cache.save(self.art5, 'art5')

        art4_path = str(self.cache.path) + ':art4'
        art5_path = str(self.cache.path) + ':art5'
        output = str(self.cache.path) + ':output'

        result = self._run_command(
            'list-of-ints', '--i-ints', art4_path, '--i-ints', art5_path,
            '--o-output', output, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = self.cache.load_collection('output')
        loaded_key = self.cache.read_key('output')

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)

        self.assertEqual(loaded_key['order'],
                         [{'0': str(collection['0'].uuid)},
                          {'1': str(collection['1'].uuid)}])

    def test_de_facto_dict_keyed(self):
        self.cache.save(self.art4, 'art4')
        self.cache.save(self.art5, 'art5')

        art4_path = str(self.cache.path) + ':art4'
        art5_path = str(self.cache.path) + ':art5'
        output = str(self.cache.path) + ':output'

        result = self._run_command(
            'dict-of-ints', '--i-ints', f'foo:{art4_path}', '--i-ints',
            f'bar:{art5_path}', '--o-output', output, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = self.cache.load_collection('output')
        loaded_key = self.cache.read_key('output')

        self.assertEqual(collection['foo'].view(int), 0)
        self.assertEqual(collection['bar'].view(int), 1)

        self.assertEqual(loaded_key['order'],
                         [{'foo': str(collection['foo'].uuid)},
                          {'bar': str(collection['bar'].uuid)}])

    def test_de_facto_dict_unkeyed(self):
        self.cache.save(self.art4, 'art4')
        self.cache.save(self.art5, 'art5')

        art4_path = str(self.cache.path) + ':art4'
        art5_path = str(self.cache.path) + ':art5'
        output = str(self.cache.path) + ':output'

        result = self._run_command(
            'dict-of-ints', '--i-ints', art4_path, '--i-ints', art5_path,
            '--o-output', output, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = self.cache.load_collection('output')
        loaded_key = self.cache.read_key('output')

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)

        self.assertEqual(loaded_key['order'],
                         [{'0': str(collection['0'].uuid)},
                          {'1': str(collection['1'].uuid)}])

    def test_mixed_cached_uncached_inputs(self):
        art4_path = os.path.join(self.tempdir, 'art4.qza')
        self.art4.save(art4_path)

        self.cache.save(self.art5, 'art5')
        art5_path = str(self.cache.path) + ':art5'

        output = str(self.cache.path) + ':output'

        result = self._run_command(
            'dict-of-ints', '--i-ints', art4_path, '--i-ints',
            art5_path,'--o-output', output, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = self.cache.load_collection('output')
        loaded_key = self.cache.read_key('output')

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)

        self.assertEqual(loaded_key['order'],
                         [{'0': str(collection['0'].uuid)},
                          {'1': str(collection['1'].uuid)}])

        self.cache.remove('output')

        result = self._run_command(
            'dict-of-ints', '--i-ints', f'foo:{art4_path}', '--i-ints',
            f'bar:{art5_path}','--o-output', output, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = self.cache.load_collection('output')
        loaded_key = self.cache.read_key('output')

        self.assertEqual(collection['foo'].view(int), 0)
        self.assertEqual(collection['bar'].view(int), 1)

        self.assertEqual(loaded_key['order'],
                         [{'foo': str(collection['foo'].uuid)},
                          {'bar': str(collection['bar'].uuid)}])

    def test_mixed_keyed_unkeyed_inputs(self):
        art4_uncached_path = os.path.join(self.tempdir, 'art4.qza')
        self.art4.save(art4_uncached_path)

        self.cache.save(self.art4, 'art4')
        self.cache.save(self.art5, 'art5')

        art4_path = str(self.cache.path) + ':art4'
        art5_path = str(self.cache.path) + ':art5'
        output = str(self.cache.path) + ':output'

        result = self._run_command(
            'dict-of-ints', '--i-ints', f'foo:{art4_path}', '--i-ints',
            art5_path,'--o-output', output, '--verbose'
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn('Keyed values cannot be mixed with unkeyed values.',
                      str(result.exception))

        result = self._run_command(
            'dict-of-ints', '--i-ints', f'foo:{art4_uncached_path}',
            '--i-ints', art5_path,'--o-output', output, '--verbose'
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn('Keyed values cannot be mixed with unkeyed values.',
                      str(result.exception))

        result = self._run_command(
            'dict-of-ints', '--i-ints', f'foo:{art4_path}',
            '--i-ints', art4_uncached_path,'--o-output', output, '--verbose'
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn('Keyed values cannot be mixed with unkeyed values.',
                      str(result.exception))

    def test_nonexistent_input_key(self):
        art1_path = str(self.cache.path) + ':art1'
        left_path = str(self.cache.path) + ':left'

        result = self._run_command(
            'split-ints', '--i-ints', art1_path, '--o-left', left_path,
            '--o-right', self.non_cache_output, '--verbose'
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn("does not contain the key 'art1'",
                      str(result.output))

    def test_output_key_invalid(self):
        self.cache.save(self.art1, 'art1')
        self.cache.save(self.art2, 'art2')
        self.cache.save(self.art3, 'art3')

        art1_path = str(self.cache.path) + ':art1'
        art2_path = str(self.cache.path) + ':art2'
        art3_path = str(self.cache.path) + ':art3'

        out_path = str(self.cache.path) + ':not_valid_identifier$&;'

        result = self._run_command(
            'concatenate-ints', '--i-ints1', art1_path, '--i-ints2', art2_path,
            '--i-ints3', art3_path, '--p-int1', '9', '--p-int2', '10',
            '--o-concatenated-ints', out_path, '--verbose'
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn('Keys must be valid Python identifiers',
                      str(result.exception))

    def test_artifact_as_metadata_cache(self):
        self.cache.save(self.mapping, 'mapping')
        mapping_path = str(self.cache.path) + ':mapping'

        result = self.runner.invoke(tools, ['inspect-metadata', mapping_path])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('COLUMN NAME  TYPE', result.output)
        self.assertIn("===========  ===========", result.output)
        self.assertIn("a  categorical", result.output)
        self.assertIn("b  categorical", result.output)
        self.assertIn("IDS:  1", result.output)
        self.assertIn("COLUMNS:  2", result.output)

    def test_artifact_as_metadata_cache_bad_key(self):
        mapping_path = str(self.cache.path) + ':mapping'

        result = self.runner.invoke(tools, ['inspect-metadata', mapping_path])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("does not contain the key 'mapping'", result.output)

    def test_artifact_as_metadata_cache_bad_cache(self):
        result = self.runner.invoke(
            tools, ['inspect-metadata', 'not_a_cache:key'])

        self.assertEqual(result.exit_code, 1)
        self.assertIn('is not a valid cache', result.output)

    def test_output_dir_as_cache(self):
        self.cache.save(self.art1, 'art1')
        self.cache.save(self.art2, 'art2')
        self.cache.save(self.art3, 'art3')

        art1_path = str(self.cache.path) + ':art1'
        art2_path = str(self.cache.path) + ':art2'
        art3_path = str(self.cache.path) + ':art3'

        out_path = str(self.cache.path) + ':out'

        result = self._run_command(
            'concatenate-ints', '--i-ints1', art1_path, '--i-ints2', art2_path,
            '--i-ints3', art3_path, '--p-int1', '9', '--p-int2', '10',
            '--output-dir', out_path, '--verbose'
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn(
            'Cache keys cannot be used as output dirs.', str(result.exception))


if __name__ == "__main__":
    unittest.main()
