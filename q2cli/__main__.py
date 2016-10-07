# ----------------------------------------------------------------------------
# Copyright (c) 2016--, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------

import click

import q2cli.commands


# TODO use  `qiime.sdk.HELP_URL` when importing qiime isn't slow.
ROOT_COMMAND_HELP = """\
QIIME 2 command-line interface (q2cli)
--------------------------------------

To get help with QIIME 2, visit http://2.qiime.org.

To enable tab completion in Bash, run the following command or add it to your \
.bashrc/.bash_profile:

    eval "$(register-qiime-completion 2> /dev/null)"

"""


# Entry point for CLI
@click.command(cls=q2cli.commands.RootCommand, invoke_without_command=True,
               no_args_is_help=True, help=ROOT_COMMAND_HELP)
@click.version_option(prog_name='q2cli',
                      message='%(prog)s version %(version)s\nRun `qiime info` '
                              'for more version details.')
def qiime():
    pass


if __name__ is '__main__':
    qiime()
