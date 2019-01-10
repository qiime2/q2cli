# ----------------------------------------------------------------------------
# Copyright (c) 2016-2019, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import click


@click.group(help='Utilities for developers and advanced users.')
def dev():
    pass


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
