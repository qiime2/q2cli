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


import_theme_help = \
    ("Allows for customization of q2cli's command line styling based on an "
     "imported .theme (INI formatted) file. If you are unfamiliar with .ini "
     "formatted files look here https://en.wikipedia.org/wiki/INI_file."
     "\n"
     "\n"
     "The .theme file allows you to customize text on the basis of what that "
     "text represents with the following supported text types: command, "
     "option, type, default_arg, required, emphasis, problem, warning, error, "
     "and success. These will be your headers in the '[]' brackets. "
     "\n"
     "\n"
     "`command` refers to the name of the command you issued. `option` refers "
     "to the arguments you give to the command when running it. `type` refers "
     "to the QIIME 2 semantic typing of these arguments (where applicable). "
     "`default_arg` refers to the label next to the argument indicating its "
     "default value (where applicable), and if it is required (where "
     "applicable). `required` refers to any arguments that must be passed to "
     "the command for it to work and gives them special formatting on top of "
     "your normal `option` formatting. `emphasis` refers to any emphasized "
     "pieces of text within help text. `problem` refers to the text informing "
     "you there were issues with the command. `warning` refers to the text "
     "for non-fatal issues while `error` refers to the text for fatal issues."
     "`success` refers to text indicating a process completed as expected."
     "\n"
     "\n"
     "Depending on what your terminal supports, some or all of the following "
     "pieces of the text's formatting may be customized: bold, dim (if true "
     "the text's brightness is reduced), underline, blink, reverse (if true "
     "foreground and background colors are reversed), and finally fg "
     "(foreground color) and bg (background color). The first five may each "
     "be either true or false, while the colors may be set to any of the "
     "following: black, red, green, yellow, blue, magenta, cyan, white, "
     "bright_black, bright_red, bright_green, bright_yellow, bright_blue, "
     "bright_magenta, bright_cyan, or bright_white.")


@dev.command(name='import-theme',
             short_help='Install new command line theme.',
             help=import_theme_help,
             cls=ToolCommand)
@click.option('--theme', required=True,
              type=click.Path(exists=True, file_okay=True,
                              dir_okay=False, readable=True),
              help='Path to file containing new theme info')
def import_theme(theme):
    import os
    import shutil
    from configparser import Error

    import q2cli.util
    from q2cli.core.config import CONFIG

    try:
        CONFIG.parse_file(theme)
    except Error as e:
        # If they tried to change [error] in a valid manner before we hit our
        # parsing error, we don't want to use their imported error settings
        CONFIG.styles = CONFIG.get_default_styles()
        header = 'Something went wrong while parsing your theme: '
        q2cli.util.exit_with_error(e, header=header, traceback=None)
    shutil.copy(theme, os.path.join(q2cli.util.get_app_dir(),
                'cli-colors.theme'))


@dev.command(name='export-default-theme',
             short_help='Export the default settings.',
             help='Create a .theme (INI formatted) file from the default '
             'settings at the specified filepath.',
             cls=ToolCommand)
@click.option('--output-path', required=True,
              type=click.Path(exists=False, file_okay=True,
                              dir_okay=False, readable=True),
              help='Path to output the config to')
def export_default_theme(output_path):
    import configparser
    from q2cli.core.config import CONFIG

    parser = configparser.ConfigParser()
    parser.read_dict(CONFIG.get_default_styles())
    with open(output_path, 'w') as fh:
        parser.write(fh)


def abort_if_false(ctx, param, value):
    if not value:
        ctx.abort()


@dev.command(name='reset-theme',
             short_help='Reset command line theme to default.',
             help="Reset command line theme to default. Requres the '--yes' "
             "parameter to be passed asserting you do want to reset.",
             cls=ToolCommand)
@click.option('--yes', is_flag=True, callback=abort_if_false,
              expose_value=False,
              prompt='Are you sure you want to reset your theme?')
def reset_theme():
    import os
    import q2cli.util

    path = os.path.join(q2cli.util.get_app_dir(), 'cli-colors.theme')
    if os.path.exists(path):
        os.unlink(path)
        click.echo('Theme reset.')
    else:
        click.echo('Theme was already default.')
