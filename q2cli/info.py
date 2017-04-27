# ----------------------------------------------------------------------------
# Copyright (c) 2016-2017, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import click


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
    import q2cli.cache

    plugins = q2cli.cache.CACHE.plugins
    if plugins:
        for name, plugin in sorted(plugins.items()):
            click.echo('%s %s' % (name, plugin['version']))
    else:
        click.secho('No plugins are currently installed.\nYou can browse '
                    'the official QIIME 2 plugins at https://qiime2.org')


def _echo_installed_packages():
    import pip

    # This code was derived from an example provide here:
    # http://stackoverflow.com/a/23885252/3424666
    installed_packages = sorted(["%s==%s" % (i.key, i.version)
                                for i in pip.get_installed_distributions()])
    for e in installed_packages:
        click.echo(e)


def _echo_citations():
    import q2cli.cache

    click.secho('\nCitations', fg='green')
    click.secho('QIIME 2 framework and command line interface', fg='cyan')
    click.secho('Pending a QIIME 2 publication, please cite QIIME using the '
                'original publication: '
                'http://www.ncbi.nlm.nih.gov/pubmed/20383131')

    plugins = q2cli.cache.CACHE.plugins
    if plugins:
        for name, plugin in sorted(plugins.items()):
            click.secho('\n%s %s' % (name, plugin['version']), fg='cyan')
            click.secho(plugin['citation_text'])
    else:
        click.secho('\nNo plugins are currently installed.\nYou can browse '
                    'the official QIIME 2 plugins at https://qiime2.org')


@click.command(help='Display information about current deployment.')
@click.option('--citations', is_flag=True,
              help='Display citations for QIIME 2 and installed plugins.')
@click.option('--py-packages', is_flag=True,
              help='Display names and versions of all installed Python '
                   'packages.')
def info(citations, py_packages):
    import q2cli.util
    import q2cli.cache

    click.secho('System versions', fg='green')
    _echo_version()
    click.secho('\nInstalled plugins', fg='green')
    _echo_plugins()
    if py_packages:
        click.secho('\nInstalled Python packages', fg='green')
        _echo_installed_packages()

    click.secho('\nApplication config directory', fg='green')
    click.secho(q2cli.util.get_app_dir())

    click.secho('\nGetting help', fg='green')
    click.secho('To get help with QIIME 2, visit https://qiime2.org')

    click.secho('\nCiting QIIME 2', fg='green')
    click.secho('If you use QIIME 2 in any published work, you should cite '
                'QIIME 2 and the plugins that you used. ', nl=False)

    if citations:
        click.secho('The citations for QIIME 2 and all installed plugins '
                    'follow.')
        _echo_citations()
    else:
        click.secho('To display the citations for QIIME 2 and all installed '
                    'plugins, run:')
        click.secho('\n  qiime info --citations\n')
