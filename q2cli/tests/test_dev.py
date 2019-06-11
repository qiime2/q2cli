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
    def setUp(self):
        self.path = os.path.join(q2cli.util.get_app_dir(), 'cli-colors.theme')
        self.old_settigs = configparser.ConfigParser()
        if os.path.exists(self.path):
            self.old_settigs.read(self.path)

        config = configparser.ConfigParser()

        self.runner = CliRunner()
        self.tempdir = tempfile.mkdtemp(prefix='qiime2-q2cli-test-temp-')

        self.config = os.path.join(self.tempdir, 'good-config.ini')
        config['type'] = {'underline': 't'}
        with open(self.config, 'w') as fh:
            config.write(fh)

    def tearDown(self):
        if os.path.exists(self.path):
            with open(self.path, 'w') as fh:
                self.old_settigs.write(fh)

    def test_install_theme(self):
        result = self.runner.invoke(
            dev, ['install-q2cli-theme', '--theme', self.config])
        self.assertEqual(result.exit_code, 0)

    def test_restore_theme(self):
        result = self.runner.invoke(
            dev, ['reset-theme'])
        self.assertEqual(result.exit_code, 0)
