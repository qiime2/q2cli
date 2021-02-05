# ----------------------------------------------------------------------------
# Copyright (c) 2016-2021, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import click

import q2cli.commands


ROOT_COMMAND_HELP = """\
QIIME 2 command-line interface (q2cli)
--------------------------------------

To get help with QIIME 2, visit https://qiime2.org.

To enable tab completion in Bash, run the following command or add it to your \
.bashrc/.bash_profile:

    source tab-qiime

To enable tab completion in ZSH, run the following commands or add them to \
your .zshrc:

    autoload bashcompinit && bashcompinit && source tab-qiime

"""


# Entry point for CLI
@click.command(cls=q2cli.commands.RootCommand, invoke_without_command=True,
               no_args_is_help=True, help=ROOT_COMMAND_HELP)
@click.version_option(prog_name='q2cli',
                      message='%(prog)s version %(version)s\nRun `qiime info` '
                              'for more version details.')
def qiime():
    pass


if __name__ == '__main__':
    qiime()
