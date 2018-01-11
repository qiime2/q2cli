# ----------------------------------------------------------------------------
# Copyright (c) 2016-2018, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import os.path
import shutil
import tempfile
import unittest

import click
from click.testing import CliRunner
from qiime2 import Artifact
from qiime2.core.testing.type import IntSequence1
from qiime2.core.testing.util import get_dummy_plugin

import q2cli
import q2cli.info
import q2cli.tools
from q2cli.commands import RootCommand


class TestOption(unittest.TestCase):
    def setUp(self):
        get_dummy_plugin()
        self.runner = CliRunner()
        self.tempdir = tempfile.mkdtemp(prefix='qiime2-q2cli-test-temp-')

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _assertRepeatedOptionError(self, result, option):
        self.assertEqual(result.exit_code, 1)
        self.assertTrue(result.output.startswith('Usage:'))
        self.assertIn('%s was specified multiple times' % option,
                      result.output)

    def test_repeated_eager_option_with_callback(self):
        result = self.runner.invoke(
            q2cli.tools.tools,
            ['import', '--show-importable-types', '--show-importable-types'])

        self._assertRepeatedOptionError(result, '--show-importable-types')

    def test_repeated_builtin_flag(self):
        result = self.runner.invoke(
            q2cli.info.info,
            ['info', '--py-packages', '--py-packages'])

        self._assertRepeatedOptionError(result, '--py-packages')

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
            q2cli.tools.tools,
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


class TestOptionDecorator(unittest.TestCase):
    def test_cls_override(self):
        with self.assertRaisesRegex(ValueError, 'override `cls=q2cli.Option`'):
            q2cli.option('--bar', cls=click.Option)
