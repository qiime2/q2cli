# ----------------------------------------------------------------------------
# Copyright (c) 2016--, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------

import click

import q2cli.commands


# Entry point for CLI
@click.command(cls=q2cli.commands.RootCommand, invoke_without_command=True,
               no_args_is_help=True)
@click.version_option(prog_name='q2cli',
                      message='%(prog)s version %(version)s\nRun `qiime info` '
                              'for more version details.')
def qiime():
    pass


if __name__ is '__main__':
    qiime()
