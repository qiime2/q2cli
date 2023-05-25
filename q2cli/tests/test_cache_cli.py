# ----------------------------------------------------------------------------
# Copyright (c) 2016-2023, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import ast
import shutil
import os.path
import unittest
import unittest.mock
import tempfile
import pkg_resources

from click.testing import CliRunner
from qiime2.core.testing.type import (IntSequence1, IntSequence2, Mapping,
                                      SingleInt)
from qiime2.core.testing.util import get_dummy_plugin
from qiime2.core.util import load_action_yaml
from qiime2.core.cache import Cache

from q2cli.commands import RootCommand
from q2cli.builtin.tools import tools
from q2cli.util import get_default_recycle_pool
from qiime2.sdk import Artifact, Visualization, ResultCollection
from qiime2.sdk.parallel_config import PARALLEL_CONFIG


# What to split the errors raised by intentionally failed pipeline on to get
# at the uuids needed for testing
FIRST_SPLIT = 'Plugin error from dummy-plugin:\n\n  '
SECOND_SPLIT = '\n\nSee above for debug info.'


def get_data_path(filename):
    return pkg_resources.resource_filename('q2cli.tests', 'data/%s' % filename)


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
        self.ints1 = {'1': self.art4, '2': self.art5}
        self.ints2 = {'1': self.art1, '2': self.art2}
        self.mapping = Artifact.import_data(Mapping, {'a': '1', 'b': '2'})

        self.metadata = os.path.join(self.tempdir, 'metadata.tsv')
        with open(self.metadata, 'w') as fh:
            fh.write('#SampleID\tcol1\n0\tfoo\nid1\tbar\n')

        self.non_cache_output = os.path.join(self.tempdir, 'output.qza')
        self.art3_non_cache = os.path.join(self.tempdir, 'art3.qza')

        # Ensure default state prior to test
        PARALLEL_CONFIG.parallel_config = None
        PARALLEL_CONFIG.action_executor_mapping = {}

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

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['0', '1'])

        result = self._run_command(
            'list-of-ints', '--i-ints', collection_out1, '--o-output',
            collection_out2, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = self.cache.load_collection(key2)

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['0', '1'])

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

        self.assertEqual(collection['foo'].view(int), 0)
        self.assertEqual(collection['bar'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['foo', 'bar'])

        result = self._run_command(
            'dict-of-ints', '--i-ints', collection_out1, '--o-output',
            collection_out2, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = self.cache.load_collection(key2)

        self.assertEqual(collection['foo'].view(int), 0)
        self.assertEqual(collection['bar'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['foo', 'bar'])

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

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['0', '1'])

        result = self._run_command(
            'dict-of-ints', '--i-ints', collection_out1, '--o-output',
            collection_out2, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = self.cache.load_collection(key2)

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['0', '1'])

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

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['0', '1'])

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

        self.assertEqual(collection['foo'].view(int), 0)
        self.assertEqual(collection['bar'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['foo', 'bar'])

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

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['0', '1'])

    def test_mixed_cached_uncached_inputs(self):
        art4_path = os.path.join(self.tempdir, 'art4.qza')
        self.art4.save(art4_path)

        self.cache.save(self.art5, 'art5')
        art5_path = str(self.cache.path) + ':art5'

        output = str(self.cache.path) + ':output'

        result = self._run_command(
            'dict-of-ints', '--i-ints', art4_path, '--i-ints',
            art5_path, '--o-output', output, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = self.cache.load_collection('output')

        self.assertEqual(collection['0'].view(int), 0)
        self.assertEqual(collection['1'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['0', '1'])

        self.cache.remove('output')

        result = self._run_command(
            'dict-of-ints', '--i-ints', f'foo:{art4_path}', '--i-ints',
            f'bar:{art5_path}', '--o-output', output, '--verbose'
        )

        self.assertEqual(result.exit_code, 0)
        collection = self.cache.load_collection('output')

        self.assertEqual(collection['foo'].view(int), 0)
        self.assertEqual(collection['bar'].view(int), 1)
        self.assertEqual(list(collection.keys()), ['foo', 'bar'])

    def test_pipeline_resumption_default(self):
        plugin_action = 'dummy_plugin_resumable_varied_pipeline'
        default_pool = get_default_recycle_pool(plugin_action)
        default_pool_fp = os.path.join(self.cache.pools, default_pool)
        output = os.path.join(self.tempdir, 'output')

        self.cache.save_collection(self.ints1, 'ints1')
        self.cache.save_collection(self.ints2, 'ints2')
        self.cache.save(self.art4, 'int1')

        ints1_path = str(self.cache.path) + ':ints1'
        ints2_path = str(self.cache.path) + ':ints2'
        int1_path = str(self.cache.path) + ':int1'

        result = self._run_command(
            'resumable-varied-pipeline', '--i-ints1', ints1_path, '--i-ints2',
            ints2_path, '--i-int1', int1_path, '--p-string', 'Hi',
            '--m-metadata-file', self.metadata, '--p-fail', 'True',
            '--output-dir', output, '--use-cache', str(self.cache.path),
            '--verbose'
        )

        self.assertEqual(result.exit_code, 1)
        # Assert that the pool exists
        self.assertTrue(os.path.exists(default_pool_fp))

        exception = result.output.split(FIRST_SPLIT)[-1]
        exception = exception.split(SECOND_SPLIT)[0]

        ints1_uuids, ints2_uuids, int1_uuid, list_uuids, dict_uuids, \
            identity_uuid, viz_uuid = ast.literal_eval(exception)

        result = self._run_command(
            'resumable-varied-pipeline', '--i-ints1', ints1_path, '--i-ints2',
            ints2_path, '--i-int1', int1_path, '--p-string', 'Hi',
            '--m-metadata-file', self.metadata, '--output-dir', output,
            '--use-cache', str(self.cache.path), '--verbose'
        )

        self.assertEqual(result.exit_code, 0)

        ints1_ret_fp = os.path.join(output, 'ints1_ret')
        ints2_ret_fp = os.path.join(output, 'ints2_ret')
        int1_ret_fp = os.path.join(output, 'int1_ret.qza')
        list_ret_fp = os.path.join(output, 'list_ret')
        dict_ret_fp = os.path.join(output, 'dict_ret')
        identity_ret_fp = os.path.join(output, 'identity_ret.qza')
        viz_ret_fp = os.path.join(output, 'viz.qzv')

        ints1_ret = ResultCollection.load(ints1_ret_fp)
        ints2_ret = ResultCollection.load(ints2_ret_fp)
        int1_ret = Artifact.load(int1_ret_fp)
        list_ret = ResultCollection.load(list_ret_fp)
        dict_ret = ResultCollection.load(dict_ret_fp)
        identity_ret = Artifact.load(identity_ret_fp)
        viz_ret = Visualization.load(viz_ret_fp)

        complete_ints1_uuids = self._load_alias_uuids(ints1_ret)
        complete_ints2_uuids = self._load_alias_uuids(ints2_ret)
        complete_int1_uuid = self._load_alias_uuid(int1_ret)
        complete_list_uuids = self._load_alias_uuids(list_ret)
        complete_dict_uuids = self._load_alias_uuids(dict_ret)
        complete_identity_uuid = self._load_alias_uuid(identity_ret)
        complete_viz_uuid = self._load_alias_uuid(viz_ret)

        # Assert that the artifacts returned by the completed run of the
        # pipeline are aliases of the artifacts created by the first failed run
        self.assertEqual(ints1_uuids, complete_ints1_uuids)
        self.assertEqual(ints2_uuids, complete_ints2_uuids)
        self.assertEqual(int1_uuid, complete_int1_uuid)
        self.assertEqual(list_uuids, complete_list_uuids)
        self.assertEqual(dict_uuids, complete_dict_uuids)
        self.assertEqual(identity_uuid, complete_identity_uuid)
        self.assertEqual(viz_uuid, complete_viz_uuid)

        # Assert that the pool was removed
        self.assertFalse(os.path.exists(default_pool_fp))

    def test_pipeline_resumption_different_pool(self):
        pool = 'pool'
        pool_fp = os.path.join(self.cache.pools, pool)
        output = os.path.join(self.tempdir, 'output')

        self.cache.save_collection(self.ints1, 'ints1')
        self.cache.save_collection(self.ints2, 'ints2')
        self.cache.save(self.art4, 'int1')

        ints1_path = str(self.cache.path) + ':ints1'
        ints2_path = str(self.cache.path) + ':ints2'
        int1_path = str(self.cache.path) + ':int1'

        result = self._run_command(
            'resumable-varied-pipeline', '--i-ints1', ints1_path, '--i-ints2',
            ints2_path, '--i-int1', int1_path, '--p-string', 'Hi',
            '--m-metadata-file', self.metadata, '--p-fail', 'True',
            '--output-dir', output, '--recycle-pool', pool, '--use-cache',
            str(self.cache.path), '--verbose'
        )

        self.assertEqual(result.exit_code, 1)
        # Assert that the pool exists
        self.assertTrue(os.path.exists(pool_fp))

        exception = result.output.split(FIRST_SPLIT)[-1]
        exception = exception.split(SECOND_SPLIT)[0]

        ints1_uuids, ints2_uuids, int1_uuid, list_uuids, dict_uuids, \
            identity_uuid, viz_uuid = ast.literal_eval(exception)

        result = self._run_command(
            'resumable-varied-pipeline', '--i-ints1', ints1_path, '--i-ints2',
            ints2_path, '--i-int1', int1_path, '--p-string', 'Hi',
            '--m-metadata-file', self.metadata, '--output-dir', output,
            '--recycle-pool', pool, '--use-cache', str(self.cache.path),
            '--verbose'
        )

        self.assertEqual(result.exit_code, 0)

        ints1_ret_fp = os.path.join(output, 'ints1_ret')
        ints2_ret_fp = os.path.join(output, 'ints2_ret')
        int1_ret_fp = os.path.join(output, 'int1_ret.qza')
        list_ret_fp = os.path.join(output, 'list_ret')
        dict_ret_fp = os.path.join(output, 'dict_ret')
        identity_ret_fp = os.path.join(output, 'identity_ret.qza')
        viz_ret_fp = os.path.join(output, 'viz.qzv')

        ints1_ret = ResultCollection.load(ints1_ret_fp)
        ints2_ret = ResultCollection.load(ints2_ret_fp)
        int1_ret = Artifact.load(int1_ret_fp)
        list_ret = ResultCollection.load(list_ret_fp)
        dict_ret = ResultCollection.load(dict_ret_fp)
        identity_ret = Artifact.load(identity_ret_fp)
        viz_ret = Visualization.load(viz_ret_fp)

        complete_ints1_uuids = self._load_alias_uuids(ints1_ret)
        complete_ints2_uuids = self._load_alias_uuids(ints2_ret)
        complete_int1_uuid = self._load_alias_uuid(int1_ret)
        complete_list_uuids = self._load_alias_uuids(list_ret)
        complete_dict_uuids = self._load_alias_uuids(dict_ret)
        complete_identity_uuid = self._load_alias_uuid(identity_ret)
        complete_viz_uuid = self._load_alias_uuid(viz_ret)

        # Assert that the artifacts returned by the completed run of the
        # pipeline are aliases of the artifacts created by the first failed run
        self.assertEqual(ints1_uuids, complete_ints1_uuids)
        self.assertEqual(ints2_uuids, complete_ints2_uuids)
        self.assertEqual(int1_uuid, complete_int1_uuid)
        self.assertEqual(list_uuids, complete_list_uuids)
        self.assertEqual(dict_uuids, complete_dict_uuids)
        self.assertEqual(identity_uuid, complete_identity_uuid)
        self.assertEqual(viz_uuid, complete_viz_uuid)

        # Assert that the pool is still there
        self.assertTrue(os.path.exists(pool_fp))

    def test_pipeline_resumption_no_recycle(self):
        plugin_action = 'dummy_plugin_resumable_varied_pipeline'
        default_pool = get_default_recycle_pool(plugin_action)
        default_pool_fp = os.path.join(self.cache.pools, default_pool)
        output = os.path.join(self.tempdir, 'output')

        self.cache.save_collection(self.ints1, 'ints1')
        self.cache.save_collection(self.ints2, 'ints2')
        self.cache.save(self.art4, 'int1')

        ints1_path = str(self.cache.path) + ':ints1'
        ints2_path = str(self.cache.path) + ':ints2'
        int1_path = str(self.cache.path) + ':int1'

        result = self._run_command(
            'resumable-varied-pipeline', '--i-ints1', ints1_path, '--i-ints2',
            ints2_path, '--i-int1', int1_path, '--p-string', 'Hi',
            '--m-metadata-file', self.metadata, '--p-fail', 'True',
            '--output-dir', output, '--use-cache', str(self.cache.path),
            '--no-recycle', '--verbose'
        )

        self.assertEqual(result.exit_code, 1)
        # Assert that the pool was not created
        self.assertFalse(os.path.exists(default_pool_fp))

        exception = result.output.split(FIRST_SPLIT)[-1]
        exception = exception.split(SECOND_SPLIT)[0]

        ints1_uuids, ints2_uuids, int1_uuid, list_uuids, dict_uuids, \
            identity_uuid, viz_uuid = ast.literal_eval(exception)

        result = self._run_command(
            'resumable-varied-pipeline', '--i-ints1', ints1_path, '--i-ints2',
            ints2_path, '--i-int1', int1_path, '--p-string', 'Hi',
            '--m-metadata-file', self.metadata, '--output-dir', output,
            '--use-cache', str(self.cache.path), '--verbose'
        )

        self.assertEqual(result.exit_code, 0)

        ints1_ret_fp = os.path.join(output, 'ints1_ret')
        ints2_ret_fp = os.path.join(output, 'ints2_ret')
        int1_ret_fp = os.path.join(output, 'int1_ret.qza')
        list_ret_fp = os.path.join(output, 'list_ret')
        dict_ret_fp = os.path.join(output, 'dict_ret')
        identity_ret_fp = os.path.join(output, 'identity_ret.qza')
        viz_ret_fp = os.path.join(output, 'viz.qzv')

        ints1_ret = ResultCollection.load(ints1_ret_fp)
        ints2_ret = ResultCollection.load(ints2_ret_fp)
        int1_ret = Artifact.load(int1_ret_fp)
        list_ret = ResultCollection.load(list_ret_fp)
        dict_ret = ResultCollection.load(dict_ret_fp)
        identity_ret = Artifact.load(identity_ret_fp)
        viz_ret = Visualization.load(viz_ret_fp)

        complete_ints1_uuids = self._load_alias_uuids(ints1_ret)
        complete_ints2_uuids = self._load_alias_uuids(ints2_ret)
        complete_int1_uuid = self._load_alias_uuid(int1_ret)
        complete_list_uuids = self._load_alias_uuids(list_ret)
        complete_dict_uuids = self._load_alias_uuids(dict_ret)
        complete_identity_uuid = self._load_alias_uuid(identity_ret)
        complete_viz_uuid = self._load_alias_uuid(viz_ret)

        # Assert that the artifacts returned by the completed run of the
        # pipeline are aliases of the artifacts created by the first failed run
        self.assertNotEqual(ints1_uuids, complete_ints1_uuids)
        self.assertNotEqual(ints2_uuids, complete_ints2_uuids)
        self.assertNotEqual(int1_uuid, complete_int1_uuid)
        self.assertNotEqual(list_uuids, complete_list_uuids)
        self.assertNotEqual(dict_uuids, complete_dict_uuids)
        self.assertNotEqual(identity_uuid, complete_identity_uuid)
        self.assertNotEqual(viz_uuid, complete_viz_uuid)

        # Assert that the pool was removed
        self.assertFalse(os.path.exists(default_pool_fp))

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
            art5_path, '--o-output', output, '--verbose'
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn('Keyed values cannot be mixed with unkeyed values.',
                      str(result.exception))

        result = self._run_command(
            'dict-of-ints', '--i-ints', f'foo:{art4_uncached_path}',
            '--i-ints', art5_path, '--o-output', output, '--verbose'
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn('Keyed values cannot be mixed with unkeyed values.',
                      str(result.exception))

        result = self._run_command(
            'dict-of-ints', '--i-ints', f'foo:{art4_path}',
            '--i-ints', art4_uncached_path, '--o-output', output, '--verbose'
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

    def test_parallel(self):
        output = os.path.join(self.tempdir, 'output')

        self.cache.save_collection(self.ints1, 'ints1')
        ints1_path = str(self.cache.path) + ':ints1'

        result = self._run_command(
            'resumable-pipeline', '--i-int-list', ints1_path,
            '--i-int-dict', ints1_path, '--output-dir', output, '--use-cache',
            str(self.cache.path), '--verbose', '--parallel'
        )

        self.assertEqual(result.exit_code, 0)

        list_return = ResultCollection.load(
            os.path.join(output, 'list_return'))
        dict_return = ResultCollection.load(
            os.path.join(output, 'dict_return'))

        list_execution_contexts = self._load_alias_execution_contexts(
            list_return)
        dict_execution_contexts = self._load_alias_execution_contexts(
            dict_return)

        expected = [{
            'type': 'parsl', 'parsl_type': 'ThreadPoolExecutor'}, {
            'type': 'parsl', 'parsl_type': 'ThreadPoolExecutor'
        }]

        self.assertEqual(list_execution_contexts, expected)
        self.assertEqual(dict_execution_contexts, expected)

    def test_config_parallel(self):
        output = os.path.join(self.tempdir, 'output')

        self.cache.save_collection(self.ints1, 'ints1')
        ints1_path = str(self.cache.path) + ':ints1'

        config_path = get_data_path('mapping_config.toml')

        result = self._run_command(
            'resumable-pipeline', '--i-int-list', ints1_path,
            '--i-int-dict', ints1_path, '--output-dir', output, '--use-cache',
            str(self.cache.path), '--verbose', '--parallel-config', config_path
        )

        self.assertEqual(result.exit_code, 0)

        list_return = ResultCollection.load(
            os.path.join(output, 'list_return'))
        dict_return = ResultCollection.load(
            os.path.join(output, 'dict_return'))

        list_execution_contexts = self._load_alias_execution_contexts(
            list_return)
        dict_execution_contexts = self._load_alias_execution_contexts(
            dict_return)

        list_expected = [{
            'type': 'parsl', 'parsl_type': 'HighThroughputExecutor'}, {
            'type': 'parsl', 'parsl_type': 'HighThroughputExecutor'
        }]
        dict_expected = [{
            'type': 'parsl', 'parsl_type': 'ThreadPoolExecutor'}, {
            'type': 'parsl', 'parsl_type': 'ThreadPoolExecutor'
        }]

        self.assertEqual(list_execution_contexts, list_expected)
        self.assertEqual(dict_execution_contexts, dict_expected)

    def test_both_parallel_flags(self):
        output = os.path.join(self.tempdir, 'output')

        self.cache.save_collection(self.ints1, 'ints1')
        ints1_path = str(self.cache.path) + ':ints1'

        config_path = get_data_path('mapping_config.toml')

        result = self._run_command(
            'resumable-pipeline', '--i-int-list', ints1_path,
            '--i-int-dict', ints1_path, '--output-dir', output, '--use-cache',
            str(self.cache.path), '--verbose', '--parallel',
            '--parallel-config', config_path
        )

        self.assertEqual(result.exit_code, 0)

        list_return = ResultCollection.load(
            os.path.join(output, 'list_return'))
        dict_return = ResultCollection.load(
            os.path.join(output, 'dict_return'))

        list_execution_contexts = self._load_alias_execution_contexts(
            list_return)
        dict_execution_contexts = self._load_alias_execution_contexts(
            dict_return)

        # The explicit config should override the default
        list_expected = [{
            'type': 'parsl', 'parsl_type': 'HighThroughputExecutor'}, {
            'type': 'parsl', 'parsl_type': 'HighThroughputExecutor'
        }]
        dict_expected = [{
            'type': 'parsl', 'parsl_type': 'ThreadPoolExecutor'}, {
            'type': 'parsl', 'parsl_type': 'ThreadPoolExecutor'
        }]

        self.assertEqual(list_execution_contexts, list_expected)
        self.assertEqual(dict_execution_contexts, dict_expected)

    def test_parallel_flags_on_non_pipeline(self):
        self.cache.save(self.art1, 'art1')
        self.cache.save(self.art2, 'art2')
        self.cache.save(self.art3, 'art3')

        art1_path = str(self.cache.path) + ':art1'
        art2_path = str(self.cache.path) + ':art2'
        art3_path = str(self.cache.path) + ':art3'

        output = str(self.cache.path) + ':output'

        result = self._run_command(
            'concatenate-ints', '--i-ints1', art1_path, '--i-ints2', art2_path,
            '--i-ints3', art3_path, '--p-int1', '9', '--p-int2', '10',
            '--o-concatenated-ints', output, '--verbose', '--parallel'
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn('No such option: --parallel', result.output)

        config_path = get_data_path('mapping_config.toml')

        result = self._run_command(
            'concatenate-ints', '--i-ints1', art1_path, '--i-ints2', art2_path,
            '--i-ints3', art3_path, '--p-int1', '9', '--p-int2', '10',
            '--o-concatenated-ints', output, '--verbose', '--parallel-config',
            config_path
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn('No such option: --parallel-config', result.output)

    def _load_alias_execution_contexts(self, collection):
        execution_contexts = []

        for result in collection.values():
            alias_uuid = load_action_yaml(
                result._archiver.path)['action']['alias-of']
            execution_contexts.append(load_action_yaml(
                self.cache.data / alias_uuid)
                ['execution']['execution_context'])

        return execution_contexts

    def _load_alias_uuid(self, result):
        return load_action_yaml(result._archiver.path)['action']['alias-of']

    def _load_alias_uuids(self, collection):
        uuids = []

        for artifact in collection.values():
            uuids.append(load_action_yaml(
                artifact._archiver.path)['action']['alias-of'])

        return uuids


if __name__ == "__main__":
    unittest.main()
