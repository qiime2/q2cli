# ----------------------------------------------------------------------------
# Copyright (c) 2016--, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------

import click

import q2cli.commands
import q2cli.info


# Entry point for CLI
@click.command(cls=q2cli.commands.RootCommand, invoke_without_command=True,
               no_args_is_help=True)
@click.option('--version', is_flag=True, callback=q2cli.info.echo_version,
              help='Print the version and exit.', expose_value=False)
def cli():
    pass


if __name__ is '__main__':
    cli()
