# ----------------------------------------------------------------------------
# Copyright (c) 2016-2019, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import os.path
import shutil
import tempfile
import unittest
import configparser

from click.testing import CliRunner
from qiime2 import Artifact
from qiime2.core.testing.type import IntSequence1
from qiime2.core.testing.util import get_dummy_plugin

import q2cli
import q2cli.util
import q2cli.builtin.info
import q2cli.builtin.tools
from q2cli.commands import RootCommand
from q2cli.core.config import CLIConfig


class TestOption(unittest.TestCase):
    def setUp(self):
        get_dummy_plugin()
        self.runner = CliRunner()
        self.tempdir = tempfile.mkdtemp(prefix='qiime2-q2cli-test-temp-')

        self.parser = configparser.ConfigParser()
        self.path = os.path.join(q2cli.util.get_app_dir(), 'cli-colors.theme')

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _assertRepeatedOptionError(self, result, option):
        self.assertEqual(result.exit_code, 1)
        self.assertTrue(result.output.startswith('Usage:'))
        self.assertRegex(result.output, '.*%s.* was specified multiple times'
                         % option)

    def test_repeated_eager_option_with_callback(self):
        result = self.runner.invoke(
            q2cli.builtin.tools.tools,
            ['import', '--show-importable-types', '--show-importable-types'])

        self._assertRepeatedOptionError(result, '--show-importable-types')

    def test_repeated_builtin_flag(self):
        result = self.runner.invoke(
            q2cli.builtin.tools.tools,
            ['import', '--input-path', 'a', '--input-path', 'b'])

        self._assertRepeatedOptionError(result, '--input-path')

    def test_repeated_action_flag(self):
        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')
        out_path = os.path.join(self.tempdir, 'out.qza')

        result = self.runner.invoke(
            command, ['no-input-method', '--o-out', out_path,
                      '--verbose', '--verbose'])

        self._assertRepeatedOptionError(result, '--verbose')

    def test_repeated_builtin_option(self):
        input_path = os.path.join(self.tempdir, 'ints.txt')
        with open(input_path, 'w') as f:
            f.write('42\n43\n44\n')
        output_path = os.path.join(self.tempdir, 'out.qza')

        result = self.runner.invoke(
            q2cli.builtin.tools.tools,
            ['import', '--input-path', input_path,
             '--output-path', output_path, '--type', 'IntSequence1',
             '--type', 'IntSequence1'])

        self._assertRepeatedOptionError(result, '--type')

    def test_repeated_action_option(self):
        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')
        out_path = os.path.join(self.tempdir, 'out.qza')

        result = self.runner.invoke(
            command, ['no-input-method', '--o-out', out_path,
                      '--o-out', out_path])

        self._assertRepeatedOptionError(result, '--o-out')

    def test_repeated_multiple_option(self):
        input_path = os.path.join(self.tempdir, 'ints.qza')
        artifact = Artifact.import_data(IntSequence1, [0, 42, 43], list)
        artifact.save(input_path)

        metadata_path1 = os.path.join(self.tempdir, 'metadata1.tsv')
        with open(metadata_path1, 'w') as f:
            f.write('id\tcol1\nid1\tfoo\nid2\tbar\n')
        metadata_path2 = os.path.join(self.tempdir, 'metadata2.tsv')
        with open(metadata_path2, 'w') as f:
            f.write('id\tcol2\nid1\tbaz\nid2\tbaa\n')

        output_path = os.path.join(self.tempdir, 'out.qza')

        qiime_cli = RootCommand()
        command = qiime_cli.get_command(ctx=None, name='dummy-plugin')

        result = self.runner.invoke(
            command, ['identity-with-metadata', '--i-ints', input_path,
                      '--o-out', output_path, '--m-metadata-file',
                      metadata_path1, '--m-metadata-file', metadata_path2,
                      '--verbose'])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(os.path.exists(output_path))
        self.assertEqual(Artifact.load(output_path).view(list), [0, 42, 43])

    def test_config_expected(self):
        self.parser['type'] = {'underline': 't'}
        with open(self.path, 'w') as fh:
            self.parser.write(fh)

        config = CLIConfig()
        config.parse_file(self.path)

        self.assertEqual(
            config.styles['type'], {'underline': True})

    def test_config_bad_selector(self):
        self.parser['tye'] = {'underline': 't'}
        with open(self.path, 'w') as fh:
            self.parser.write(fh)

        config = CLIConfig()
        with self.assertRaisesRegex(
                configparser.Error, 'tye.*valid selector.*valid selectors'):
            config.parse_file(self.path)

    def test_config_bad_styling(self):
        self.parser['type'] = {'underlined': 't'}
        with open(self.path, 'w') as fh:
            self.parser.write(fh)

        config = CLIConfig()
        with self.assertRaisesRegex(
                configparser.Error, 'underlined.*valid styling.*valid '
                'stylings'):
            config.parse_file(self.path)

    def test_config_bad_color(self):
        self.parser['type'] = {'fg': 'purple'}
        with open(self.path, 'w') as fh:
            self.parser.write(fh)

        config = CLIConfig()
        with self.assertRaisesRegex(
                configparser.Error, 'purple.*valid color.*valid colors'):
            config.parse_file(self.path)

    def test_config_bad_boolean(self):
        self.parser['type'] = {'underline': 'g'}
        with open(self.path, 'w') as fh:
            self.parser.write(fh)

        config = CLIConfig()
        with self.assertRaisesRegex(
                configparser.Error, 'g.*valid boolean.*valid booleans'):
            config.parse_file(self.path)

    def test_no_file(self):
        config = CLIConfig()
        with self.assertRaisesRegex(
                configparser.Error, "'Path' is not a valid filepath."):
            config.parse_file('Path')


if __name__ == "__main__":
    unittest.main()
