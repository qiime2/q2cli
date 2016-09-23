# ----------------------------------------------------------------------------
# Copyright (c) 2016--, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------

import click


def echo_version(ctx=None, name=None, value=True):
    if value:
        # Conditional imports because this callback appears to be invoked when
        # any command is run (in most cases, `value` is `False`).
        import sys
        import qiime
        import q2cli

        pyver = sys.version_info
        click.echo('Python version: %d.%d.%d' %
                   (pyver.major, pyver.minor, pyver.micro))
        click.echo('QIIME version: %s' % qiime.__version__)
        click.echo('q2cli version: %s' % q2cli.__version__)


def _echo_plugins():
    import qiime.sdk
    import q2cli.cache

    plugins = q2cli.cache.CACHE.plugins
    if plugins:
        for name, plugin in sorted(plugins.items()):
            click.echo('%s %s' % (name, plugin['version']))
    else:
        click.secho('No plugins are currently installed.\nYou can browse '
                    'the official QIIME 2 plugins at: '
                    '%s/Plugins' % qiime.sdk.HELP_URL)


def _echo_installed_packages():
    import pip

    # This code was derived from an example provide here:
    # http://stackoverflow.com/a/23885252/3424666
    installed_packages = sorted(["%s==%s" % (i.key, i.version)
                                for i in pip.get_installed_distributions()])
    for e in installed_packages:
        click.echo(e)


@click.command(help='Display information about the current QIIME deployment.')
@click.option('--py-packages', is_flag=True,
              help='Display names and versions of all installed Python '
                   'packages.')
def info(py_packages):
    import qiime.sdk
    import q2cli.util
    import q2cli.cache

    click.secho('System versions', fg='green')
    echo_version()
    click.secho('\nInstalled plugins', fg='green')
    _echo_plugins()
    if py_packages:
        click.secho('\nInstalled Python packages', fg='green')
        _echo_installed_packages()

    click.secho('\nApplication config directory', fg='green')
    click.secho(q2cli.util.get_app_dir())

    click.secho('\nGetting help', fg='green')
    click.secho('To get help with QIIME 2, visit %s.' % qiime.sdk.HELP_URL)

    click.secho('\nCiting QIIME 2', fg='green')
    click.secho('If you use QIIME 2 in any published work, you should cite '
                'QIIME 2 and the plugins that you used. To find the relevant '
                'citations, run:')
    click.secho('\tqiime tools citations')
