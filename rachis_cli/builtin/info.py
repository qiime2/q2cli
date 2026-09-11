# ----------------------------------------------------------------------------
# Copyright (c) 2016-2026, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import click

from rachis_cli.click.command import ToolCommand


def _echo_version():
    import sys
    import rachis
    import rachis_cli

    pyver = sys.version_info
    click.echo('Python version: %d.%d.%d' %
               (pyver.major, pyver.minor, pyver.micro))
    click.echo('Parsl version: %s' % _get_parsl_ver())
    click.echo('rachis release: %s' % rachis.__release__)
    click.echo('rachis version: %s' % rachis.__version__)
    click.echo('rachis-cli version: %s' % rachis_cli.__version__)


def _get_parsl_ver():
    import os
    import pathlib
    import importlib.metadata

    conda_env_prefix = os.environ.get('CONDA_PREFIX', '')
    conda_meta_path = pathlib.Path(conda_env_prefix) / 'conda-meta'

    parsl_ver = None

    # prefer the parsl version in conda env if available
    if conda_meta_path.exists():
        for file in conda_meta_path.iterdir():
            if file.stem.startswith('parsl-'):
                # version is in the structure of: parsl-2026.2.23-pyhcf101f3_0
                parsl_ver = file.stem.split('-', 2)[1]
                break

    # fall back to any externally installed version if conda env not detectable
    # or if parsl not found in existing conda env
    if parsl_ver is None:
        try:
            parsl_ver = importlib.metadata.version('parsl')
        except importlib.metadata.PackageNotFoundError:
            pass

    return parsl_ver


def _echo_plugins():
    import rachis_cli.core.cache

    plugins = rachis_cli.core.cache.CACHE.plugins
    if plugins:
        for name, plugin in sorted(plugins.items()):
            click.echo('%s: %s' % (name, plugin['version']))
    else:
        click.secho('No plugins are currently installed.\n'
                    'Find plugins at https://library.qiime2.org.')


@click.command(help='Display information about current deployment.',
               cls=ToolCommand)
@click.option('--config-level',
              required=False,
              default=1,
              show_default=True,
              type=click.IntRange(0, 3),
              help='The level of detail to be used for displaying the '
                   'configuration summary.')
def info(config_level):
    import rachis_cli.util
    # This import improves performance for repeated _echo_plugins
    import rachis_cli.core.cache
    from rachis.sdk.parallel_config import (get_vendored_config,
                                            load_config_from_dict)
    from tomlkit import dumps

    click.secho('System versions', fg='green')
    _echo_version()
    click.secho('\nInstalled plugins', fg='green')
    _echo_plugins()

    click.secho('\nApplication config directory', fg='green')
    click.secho(rachis_cli.util.get_app_dir())

    if config_level > 0:
        click.secho('\nConfig', fg='green')

        config, action_executor_mapping, vendored_source = \
            get_vendored_config()

        click.secho(f'Config Source: {vendored_source}')

        if action_executor_mapping:
            config['parsl.executor_mapping'] = action_executor_mapping

        if config_level > 1:
            if config_level == 2:
                config = dumps(config)
            elif config_level == 3:
                config['parsl'], _ = load_config_from_dict(config)

            click.secho(f'\n{config}')

    click.secho('\nGetting help', fg='green')
    click.secho('To find help and learning resources, visit '
                'https://qiime2.org.')

    if config_level:
        click.secho('To get help with configuring and/or understanding '
                    'rachis parallelization, visit '
                    'https://use.qiime2.org/en/stable/references/'
                    'parallel-configuration.html')

    click.secho('\n')
