# ----------------------------------------------------------------------------
# Copyright (c) 2016-2019, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import click

from q2cli.click.command import ToolCommand, ToolGroupCommand


@click.group(help='Utilities for developers and advanced users.',
             cls=ToolGroupCommand)
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
                  "will always refresh the cache when a command is run.",
             cls=ToolCommand)
def refresh_cache():
    import q2cli.core.cache
    q2cli.core.cache.CACHE.refresh()


install_theme_help = \
    ("Allows for customization of q2cli's command line styling based on an "
     "imported .ini file. If you are unfamiliar with the format of .ini "
     "files look here https://en.wikipedia.org/wiki/INI_file."
     "\n"
     "\n"
     "The .ini allows you to customize text on the basis of what that text "
     "represents with the following supported text types: command, options, "
     "type, default_arg, required, emphasis, problem, errors, and success. "
     "These will be your headers in the '[]' brackets. "
     "\n"
     "\n"
     "Command refers to the name of the command you issued. Option refers "
     "to the arguments you give to the command when running it. Type refers "
     "to the Qiime2 semantic typing of these arguments (where applicable). "
     "Default_arg refers to the label next to the argument indicating its "
     "default value (where applicable), and if it is required (where "
     "applicable). Required refers to any arguments that must be passed to "
     "the command for it to work and gives them special formatting on top of "
     "your normal 'options' formatting. Emphasis refers to any emphasized "
     "pieces of text within help text. Problem refers to the text informing "
     "you there were issues with the command. Error refers to the text "
     "specifying those issues. Success refers to text indicating a process "
     "completed as expected."
     "\n"
     "\n"
     "The following pieces of the text's formatting may be customized: bold, "
     "dim (if true the text's brightness is reduced), underline, blink, "
     "reverse (if true foreground and background colors are reversed), and "
     "finally fg (foreground color) and bg (background color). The first five "
     "may each be either true or false, while the colors may be set to any of "
     "the following: black, red, green, yellow, blue, magenta, cyan, white, "
     "bright_black, bright_red, bright_green, bright_yellow, bright_blue, "
     "bright_magenta, bright_cyan, or bright_white.")


@dev.command(name='install-theme',
             short_help='Install new command line theme.',
             help=install_theme_help,
             cls=ToolCommand)
@click.option('--theme', required=True,
              type=click.Path(exists=True, file_okay=True,
                              dir_okay=False, readable=True),
              help='Path to file containing new theme info')
def install_theme(theme):
    import os
    import shutil
    import q2cli.util
    from q2cli.core.config import CONFIG
    CONFIG.parse_file(theme)
    shutil.copy(theme, os.path.join(q2cli.util.get_app_dir(),
                'cli-colors.theme'))


@dev.command(name='write-default-theme',
             short_help='Create a .ini file from the default settings at the '
             'specified filepath.',
             help='Create a .ini file from the default settings at the '
             'specified filepath.',
             cls=ToolCommand)
@click.option('--output-path', required=True,
              type=click.Path(exists=False, file_okay=True,
                              dir_okay=False, readable=True),
              help='Path to output the config to')
def write_default_theme(output_path):
    import configparser
    from q2cli.core.config import CONFIG

    # Check errors on bad paths
    parser = configparser.ConfigParser()
    parser.read_dict(CONFIG._get_default_styles())
    with open(output_path, 'w') as fh:
        parser.write(fh)


@dev.command(name='reset-theme',
             short_help='Reset command line theme to default.',
             help='Reset command line theme to default.',
             cls=ToolCommand)
def reset_theme():
    import os
    import q2cli.util
    path = os.path.join(q2cli.util.get_app_dir(), 'cli-colors.theme')
    if os.path.exists(path):
        os.unlink(path)
