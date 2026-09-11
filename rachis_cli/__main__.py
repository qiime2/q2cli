# ----------------------------------------------------------------------------
# Copyright (c) 2016-2026, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import click

import rachis_cli.commands


ROOT_COMMAND_HELP = """\
rachis command-line interface (rachis-cli)
------------------------------------------

To get help with rachis, visit https://qiime2.org.

To enable tab completion in Bash, run the following command or add it to your \
.bashrc/.bash_profile:

    source tab-rachis

To enable tab completion in ZSH, run the following commands or add them to \
your .zshrc:

\b
    autoload -Uz compinit && compinit
    autoload bashcompinit && bashcompinit
    source tab-rachis

"""


# Entry point for CLI
@click.command(cls=rachis_cli.commands.RootCommand,
               invoke_without_command=True,
               no_args_is_help=True, help=ROOT_COMMAND_HELP)
@click.version_option(package_name='rachis-cli',
                      message='%(package)s version %(version)s\n'
                              'Run `%(prog)s info` for more version details.')
def rachis():
    pass


if __name__ == '__main__':
    rachis()
