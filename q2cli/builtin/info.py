# ----------------------------------------------------------------------------
# Copyright (c) 2016-2021, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import click

from q2cli.click.command import ToolCommand


def _echo_version():
    import sys
    import qiime2
    import q2cli

    pyver = sys.version_info
    click.echo('Python version: %d.%d.%d' %
               (pyver.major, pyver.minor, pyver.micro))
    click.echo('QIIME 2 release: %s' % qiime2.__release__)
    click.echo('QIIME 2 version: %s' % qiime2.__version__)
    click.echo('q2cli version: %s' % q2cli.__version__)


def _echo_plugins():
    import q2cli.core.cache

    plugins = q2cli.core.cache.CACHE.plugins
    if plugins:
        for name, plugin in sorted(plugins.items()):
            click.echo('%s: %s' % (name, plugin['version']))
    else:
        click.secho('No plugins are currently installed.\nYou can browse '
                    'the official QIIME 2 plugins at https://qiime2.org')


@click.command(help='Display information about current deployment.',
               cls=ToolCommand)
def info():
    import q2cli.util
    # This import improves performance for repeated _echo_plugins
    import q2cli.core.cache

    click.secho('System versions', fg='green')
    _echo_version()
    click.secho('\nInstalled plugins', fg='green')
    _echo_plugins()

    click.secho('\nApplication config directory', fg='green')
    click.secho(q2cli.util.get_app_dir())

    click.secho('\nGetting help', fg='green')
    click.secho('To get help with QIIME 2, visit https://qiime2.org')
