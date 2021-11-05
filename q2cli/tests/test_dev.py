# ----------------------------------------------------------------------------
# Copyright (c) 2016-2021, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import os
import shutil
import unittest
import tempfile
import configparser

from click.testing import CliRunner
from qiime2 import Artifact
from qiime2.core.testing.type import IntSequence1
from qiime2.core.testing.util import get_dummy_plugin

import q2cli.util
from q2cli.builtin.dev import dev


class TestDev(unittest.TestCase):
    path = os.path.join(q2cli.util.get_app_dir(), 'cli-colors.theme')
    old_settings = None
    if os.path.exists(path):
        old_settings = configparser.ConfigParser()
        old_settings.read(path)

    def setUp(self):
        get_dummy_plugin()
        self.parser = configparser.ConfigParser()
        self.runner = CliRunner(mix_stderr=False)
        self.tempdir = tempfile.mkdtemp(prefix='qiime2-q2cli-test-temp-')
        self.generated_config = os.path.join(self.tempdir, 'generated-theme')

        self.tempdir = tempfile.mkdtemp(prefix='qiime2-q2cli-test-temp-')
        self.artifact1_path = os.path.join(self.tempdir, 'a1.qza')
        self.mapping_path = os.path.join(self.tempdir, 'mapping.qza')

        artifact1 = Artifact.import_data(IntSequence1, [0, 42, 43])
        artifact1.save(self.artifact1_path)
        self.artifact1_root_dir = str(artifact1.uuid)

        mapping = Artifact.import_data('Mapping', {'foo': '42'})
        mapping.save(self.mapping_path)

        self.config = os.path.join(self.tempdir, 'good-config.ini')
        self.parser['type'] = {'underline': 't'}
        with open(self.config, 'w') as fh:
            self.parser.write(fh)

    def tearDown(self):
        if self.old_settings is not None:
            with open(self.path, 'w') as fh:
                self.old_settings.write(fh)
        shutil.rmtree(self.tempdir)

    def test_import_theme(self):
        result = self.runner.invoke(
            dev, ['import-theme', '--theme', self.config])
        self.assertEqual(result.exit_code, 0)

    def test_export_default_theme(self):
        result = self.runner.invoke(
            dev, ['export-default-theme', '--output-path',
                  self.generated_config])
        self.assertEqual(result.exit_code, 0)

    def test_reset_theme(self):
        result = self.runner.invoke(
            dev, ['reset-theme', '--yes'])
        self.assertEqual(result.exit_code, 0)

    def test_reset_theme_no_yes(self):
        result = self.runner.invoke(
            dev, ['reset-theme'])
        self.assertNotEqual(result.exit_code, 0)

# result_type & result_data tests
    def test_assert_result_type_artifact_success(self):
        result = self.runner.invoke(dev,
                                    ['assert-result-type',
                                     self.mapping_path,
                                     '--qiime-type', 'Mapping'])

        # single regex to account for tempdir path
        expected_regex = r'The type of the input file: .*mapping.qza and the'\
                         r' expected type: Mapping match'

        self.assertEqual(result.exit_code, 0)
        self.assertRegex(result.stdout, expected_regex)

    def test_assert_result_type_visualization_succes(self):
        dummy_plugin = get_dummy_plugin()

        self.viz_path = os.path.join(self.tempdir, 'viz.qzv')
        most_common_viz = dummy_plugin.actions['most_common_viz']
        viz = most_common_viz(Artifact.load(self.artifact1_path))
        viz.visualization.save(self.viz_path)

        result = self.runner.invoke(dev,
                                    ['assert-result-type',
                                     self.viz_path,
                                     '--qiime-type',
                                     'Visualization'])

        expected_regex = r'The type of the input file: .*viz\.qzv and the'\
                         r' expected type: Visualization match'

        self.assertEqual(result.exit_code, 0)
        self.assertRegex(result.stdout, expected_regex)

    def test_assert_result_type_load_failure(self):
        result = self.runner.invoke(dev,
                                    ['assert-result-type',
                                     'turkey_sandwhere.qza',
                                     '--qiime-type', 'Mapping'])

        self.assertEqual(result.exit_code, 1)
        self.assertRegex(result.stderr,
                         r'File\s*\'turkey_sandwhere\.qza\'\s*does not exist')

    def test_assert_result_type_invalid_qiime_type(self):
        result = self.runner.invoke(dev,
                                    ['assert-result-type',
                                     self.mapping_path,
                                     '--qiime-type', 'Squid'])
        self.assertEqual(result.exit_code, 1)
        self.assertIn('Expected Squid, observed Mapping', result.stderr)

    def test_assert_result_data_success(self):
        result = self.runner.invoke(dev,
                                    ['assert-result-data',
                                     self.mapping_path,
                                     '--zip-data-path', 'mapping.tsv',
                                     '--expression', '42'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(r'"42" was found in mapping.tsv', result.stdout)

    def test_assert_result_data_load_failure(self):
        result = self.runner.invoke(dev,
                                    ['assert-result-data',
                                     'turkey_sandwhen.qza',
                                     '--zip-data-path', 'mapping.tsv',
                                     '--expression', '42'])

        self.assertEqual(result.exit_code, 1)
        self.assertRegex(result.stderr,
                         r'File\s*\'turkey_sandwhen\.qza\'\s*does not exist')

    def test_assert_result_data_zip_data_path_zero_matches(self):
        result = self.runner.invoke(dev,
                                    ['assert-result-data',
                                     self.mapping_path,
                                     '--zip-data-path', 'turkey_sandwhy.tsv',
                                     '--expression', '42'])

        self.assertEqual(result.exit_code, 1)
        self.assertRegex(result.stderr,
                         r'did not produce exactly one match.\n'
                         r'Matches: \[\]\n')

    def test_assert_result_data_zip_data_path_multiple_matches(self):
        self.double_path = os.path.join(self.tempdir, 'double.qza')
        double_artifact = Artifact.import_data('SingleInt', 3)
        double_artifact.save(self.double_path)
        result = self.runner.invoke(dev, ['assert-result-data',
                                          self.double_path,
                                          '--zip-data-path',
                                          'file*.txt',
                                          '--expression',
                                          '3'])
        self.assertEqual(result.exit_code, 1)
        self.assertRegex(result.stderr, r'Value provided for zip_data_path'
                                        r' \(file\*\.txt\) did not produce'
                                        r' exactly one match\.')

    def test_assert_result_data_match_expression_not_found(self):
        result = self.runner.invoke(dev, ['assert-result-data',
                                          self.mapping_path,
                                          '--zip-data-path', 'mapping.tsv',
                                          '--expression', 'foobar'])

        self.assertEqual(result.exit_code, 1)
        self.assertRegex(result.stderr,
                         r'Expression \'foobar\''
                         r' not found in mapping.tsv.')
