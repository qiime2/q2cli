# ----------------------------------------------------------------------------
# Copyright (c) 2016-2019, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import os
import unittest
import tempfile
import configparser

from click.testing import CliRunner

import q2cli.util
from q2cli.builtin.dev import dev


class TestDev(unittest.TestCase):
    path = os.path.join(q2cli.util.get_app_dir(), 'cli-colors.theme')
    old_settings = None
    if os.path.exists(path):
        old_settings = configparser.ConfigParser()
        old_settings.read(path)

    def setUp(self):
        self.parser = configparser.ConfigParser()
        self.runner = CliRunner()
        self.tempdir = tempfile.mkdtemp(prefix='qiime2-q2cli-test-temp-')
        self.generated_config = os.path.join(self.tempdir, 'generated-theme')

        self.config = os.path.join(self.tempdir, 'good-config.ini')
        self.parser['type'] = {'underline': 't'}
        with open(self.config, 'w') as fh:
            self.parser.write(fh)

    def tearDown(self):
        if self.old_settings is not None:
            with open(self.path, 'w') as fh:
                self.old_settings.write(fh)

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
