# ----------------------------------------------------------------------------
# Copyright (c) 2016--, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------

import click


@click.group(help='Utilities for developers and advanced users.')
def dev():
    pass


@dev.command(name='plugin-init',
             short_help='Initialize plugin package from template.',
             help="Initializes plugin package from template to specified"
                  " output directory. Use this command if you are a"
                  " plugin developer starting to develop a new plugin.")
@click.pass_context
@click.option('--output-dir', required=False,
              type=click.Path(exists=False, file_okay=False, dir_okay=True,
                              writable=True),
              help='Directory in which to create plugin package.',
              default='.')
def plugin_init(ctx, output_dir):
    import qiime2.plugin

    try:
        path = qiime2.plugin.plugin_init(output_dir=output_dir)
    except FileExistsError as e:
        click.secho("Plugin package directory name already exists under %s"
                    % (output_dir if output_dir != '.' else
                       'the current directory'),
                    err=True, fg='red')
        click.secho("Original error message:\n%s" % e, err=True, fg='red')
        ctx.exit(1)
    click.secho("Your plugin package has been created at %s" % path,
                fg='green')


@dev.command(name='refresh-cache',
             short_help='Refresh CLI cache.',
             help="Refresh the CLI cache. Use this command if you are "
                  "developing a plugin, or q2cli itself, and want your "
                  "changes to take effect in the CLI. A refresh of the cache "
                  "is necessary because package versions do not typically "
                  "change each time an update is made to a package's code. "
                  "Setting the environment variable Q2CLIDEV to any value "
                  "will always refresh the cache when a command is run.")
def refresh_cache():
    import q2cli.cache
    q2cli.cache.CACHE.refresh()
