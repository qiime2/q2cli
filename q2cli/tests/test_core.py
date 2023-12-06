# ----------------------------------------------------------------------------
# Copyright (c) 2016-2023, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import os.path
import pathlib
import shutil
import tempfile
import unittest
import configparser
import zipfile

import pandas as pd

from click.testing import CliRunner
from qiime2 import Artifact
from qiime2.core.testing.type import IntSequence1
from qiime2.core.testing.util import get_dummy_plugin
from qiime2.sdk.util import camel_to_snake
from qiime2.sdk.usage import UsageVariable
from qiime2.sdk import PluginManager
from qiime2.core.archive.provenance_lib import DummyArtifacts, ProvDAG
from qiime2.core.archive.provenance_lib.replay import (
    ReplayConfig, param_is_metadata_column, dump_recorded_md_file,
    NamespaceCollections, build_import_usage, build_action_usage,
    ActionCollections, replay_provenance, replay_supplement
)
from qiime2.core.archive.provenance_lib.usage_drivers import ReplayPythonUsage

import q2cli
import q2cli.util
import q2cli.builtin.info
import q2cli.builtin.tools
from q2cli.commands import RootCommand
from q2cli.core.config import CLIConfig
from q2cli.core.usage import ReplayCLIUsage, CLIUsageVariable


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
            ['list-types', '--tsv', '--tsv'])

        self._assertRepeatedOptionError(result, '--tsv')

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


class ReplayCLIUsageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.das = DummyArtifacts()
        cls.tempdir = cls.das.tempdir
        cls.pm = PluginManager()

    @classmethod
    def tearDownClass(cls):
        cls.das.free()

    def test_init_metadata(self):
        use = ReplayCLIUsage()
        var = use.init_metadata(name='testing', factory=lambda: None)
        self.assertEqual(var.name, '<your metadata filepath>')
        self.assertEqual(var.var_type, 'metadata')

    def test_init_metadata_with_dumped_md_fn(self):
        use = ReplayCLIUsage()
        var = use.init_metadata(
            name='testing', factory=lambda: None, dumped_md_fn='some_md')
        self.assertEqual(var.var_type, 'metadata')
        self.assertEqual(var.name, '"some_md.tsv"')

    def test_param_is_metadata_col(self):
        cfg = ReplayConfig(use=ReplayCLIUsage(),
                           use_recorded_metadata=False, pm=self.pm)

        actual = param_is_metadata_column(
            cfg, 'metadata', 'dummy_plugin', 'identity_with_metadata_column'
        )
        self.assertTrue(actual)

        actual = param_is_metadata_column(
            cfg, 'int1', 'dummy_plugin', 'concatenate_ints'
        )
        self.assertFalse(actual)

        with self.assertRaisesRegex(KeyError, "No action.*registered.*"):
            param_is_metadata_column(
                cfg, 'ints', 'dummy_plugin', 'young'
            )

        with self.assertRaisesRegex(KeyError, "No param.*registered.*"):
            param_is_metadata_column(
                cfg, 'thugger', 'dummy_plugin', 'split_ints'
            )

        with self.assertRaisesRegex(KeyError, "No plugin.*registered.*"):
            param_is_metadata_column(
                cfg, 'fake_param', 'dummy_hard', 'split_ints'
            )

    def test_dump_recorded_md_file_to_custom_dir(self):
        dag = self.das.int_seq_with_md.dag
        uuid = self.das.int_seq_with_md.uuid

        out_dir = 'custom_dir'
        provnode = dag.get_node_data(uuid)
        og_md = provnode.metadata['metadata']
        action_name = 'concatenate_ints_0'
        md_id = 'metadata'
        fn = 'metadata.tsv'

        with tempfile.TemporaryDirectory() as tempdir:
            cfg = ReplayConfig(use=ReplayCLIUsage(),
                               pm=self.pm,
                               md_out_dir=(tempdir + '/' + out_dir))
            dump_recorded_md_file(cfg, provnode, action_name, md_id, fn)
            out_path = pathlib.Path(tempdir) / out_dir / action_name / fn

            self.assertTrue(out_path.is_file())

            dumped_df = pd.read_csv(out_path, sep='\t')
            pd.testing.assert_frame_equal(dumped_df, og_md)

            # If we run it again, it shouldn't overwrite 'recorded_metadata',
            # so we should have two files
            action_name_2 = 'concatenate_ints_1'
            md_id2 = 'metadata'
            fn2 = 'metadata_1.tsv'
            dump_recorded_md_file(cfg, provnode, action_name_2, md_id2, fn2)
            out_path2 = pathlib.Path(tempdir) / out_dir / action_name_2 / fn2

            # are both files where expected?
            self.assertTrue(out_path.is_file())
            self.assertTrue(out_path2.is_file())

    def test_build_import_usage_cli(self):
        ns = NamespaceCollections()
        cfg = ReplayConfig(use=ReplayCLIUsage(),
                           use_recorded_metadata=False, pm=self.pm)
        dag = self.das.concated_ints_v6.dag
        import_uuid = '8dea2f1a-2164-4a85-9f7d-e0641b1db22b'
        import_node = dag.get_node_data(import_uuid)
        c_to_s_type = camel_to_snake(import_node.type)
        unq_var_nm = c_to_s_type + '_0'
        build_import_usage(import_node, ns, cfg)
        rendered = cfg.use.render()
        vars = ns.usg_vars
        out_name = vars[import_uuid].to_interface_name()

        self.assertIsInstance(vars[import_uuid], UsageVariable)
        self.assertEqual(vars[import_uuid].var_type, 'artifact')
        self.assertEqual(vars[import_uuid].name, unq_var_nm)
        self.assertRegex(rendered, r'qiime tools import \\')
        self.assertRegex(rendered, f"  --type '{import_node.type}'")
        self.assertRegex(rendered, "  --input-path <your data here>")
        self.assertRegex(rendered, f"  --output-path {out_name}")

    def test_build_action_usage_cli(self):
        plugin = 'dummy-plugin'
        action = 'concatenate-ints'
        cfg = ReplayConfig(use=ReplayCLIUsage(),
                           use_recorded_metadata=False, pm=self.pm)

        ns = NamespaceCollections()
        import_var_1 = CLIUsageVariable(
            'imported_ints_0', lambda: None, 'artifact', cfg.use
        )
        import_var_2 = CLIUsageVariable(
            'imported_ints_1', lambda: None, 'artifact', cfg.use
        )
        import_uuid_1 = '8dea2f1a-2164-4a85-9f7d-e0641b1db22b'
        import_uuid_2 = '7727c060-5384-445d-b007-b64b41a090ee'
        ns.usg_vars = {
            import_uuid_1: import_var_1,
            import_uuid_2: import_var_2
        }

        dag = self.das.concated_ints_v6.dag
        action_uuid = '5035a60e-6f9a-40d4-b412-48ae52255bb5'
        node_uuid = '6facaf61-1676-45eb-ada0-d530be678b27'
        node = dag.get_node_data(node_uuid)
        actions = ActionCollections(
            std_actions={action_uuid: {node_uuid: 'concatenated_ints'}}
        )
        unique_var_name = node.action.output_name + '_0'
        build_action_usage(node, ns, actions.std_actions, action_uuid, cfg)
        rendered = cfg.use.render()
        out_name = ns.usg_vars[node_uuid].to_interface_name()

        vars = ns.usg_vars
        self.assertIsInstance(vars[node_uuid], UsageVariable)
        self.assertEqual(vars[node_uuid].var_type, 'artifact')
        self.assertEqual(vars[node_uuid].name, unique_var_name)

        self.assertIn(f'qiime {plugin} {action}', rendered)
        self.assertIn('--i-ints1 imported-ints-0.qza', rendered)
        self.assertIn('--i-ints3 imported-ints-1.qza', rendered)
        self.assertIn('--p-int1 7', rendered)
        self.assertIn(f'--o-concatenated-ints {out_name}', rendered)

    def test_replay_optional_param_is_none(self):
        dag = self.das.int_seq_optional_input.dag
        with tempfile.TemporaryDirectory() as tempdir:
            out_path = pathlib.Path(tempdir) / 'ns_coll.txt'
            replay_provenance(ReplayCLIUsage, dag, out_path,
                              md_out_dir=tempdir)

            with open(out_path, 'r') as fp:
                rendered = fp.read()
            self.assertIn('--i-ints int-sequence1-0.qza', rendered)
            self.assertIn('--p-num1', rendered)
            self.assertNotIn('--i-optional1', rendered)
            self.assertNotIn('--p-num2', rendered)

    def test_replay_from_provdag_ns_collision(self):
        """
        This artifact's dag contains a few results with the output-name
        filtered-table, so is a good check for namespace collisions if
        we're not uniquifying variable names properly.
        """
        with tempfile.TemporaryDirectory() as tempdir:
            self.das.concated_ints.artifact.save(
                os.path.join(tempdir, 'c1.qza')
            )
            self.das.other_concated_ints.artifact.save(
                os.path.join(tempdir, 'c2.qza')
            )
            dag = ProvDAG(tempdir)

        exp = ['concatenated-ints-0', 'concatenated-ints-1']
        with tempfile.TemporaryDirectory() as tempdir:
            out_path = pathlib.Path(tempdir) / 'ns_coll.txt'
            replay_provenance(ReplayCLIUsage, dag, out_path,
                              md_out_dir=tempdir)

            with open(out_path, 'r') as fp:
                rendered = fp.read()
                for name in exp:
                    self.assertIn(name, rendered)


class WriteReproducibilitySupplementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.das = DummyArtifacts()
        cls.tempdir = cls.das.tempdir
        cls.pm = PluginManager()

    @classmethod
    def tearDownClass(cls):
        cls.das.free()

    def test_replay_supplement_from_fp(self):
        fp = self.das.concated_ints_with_md.filepath
        with tempfile.TemporaryDirectory() as tempdir:
            out_fp = os.path.join(tempdir, 'supplement.zip')
            replay_supplement(
                usage_drivers=[ReplayPythonUsage, ReplayCLIUsage],
                payload=fp,
                out_fp=out_fp
            )

            self.assertTrue(zipfile.is_zipfile(out_fp))

            exp = {
                'python3_replay.py',
                'cli_replay.sh',
                'citations.bib',
                'recorded_metadata/',
                'recorded_metadata/dummy_plugin_identity_with_metadata_0/'
                'metadata_0.tsv',
            }
            with zipfile.ZipFile(out_fp, 'r') as myzip:
                namelist_set = set(myzip.namelist())
                for item in exp:
                    self.assertIn(item, namelist_set)

    def test_replay_supplement_from_provdag(self):
        dag = self.das.concated_ints_with_md.dag

        with tempfile.TemporaryDirectory() as tempdir:
            out_fp = os.path.join(tempdir, 'supplement.zip')
            replay_supplement(
                usage_drivers=[ReplayPythonUsage, ReplayCLIUsage],
                payload=dag,
                out_fp=out_fp
            )

            self.assertTrue(zipfile.is_zipfile(out_fp))

            exp = {
                'python3_replay.py',
                'cli_replay.sh',
                'citations.bib',
                'recorded_metadata/',
                'recorded_metadata/dummy_plugin_identity_with_metadata_0/'
                'metadata_0.tsv',
            }
            with zipfile.ZipFile(out_fp, 'r') as myzip:
                namelist_set = set(myzip.namelist())
                for item in exp:
                    self.assertIn(item, namelist_set)


if __name__ == "__main__":
    unittest.main()
