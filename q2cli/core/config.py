# ----------------------------------------------------------------------------
# Copyright (c) 2016-2019, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import os
import configparser

import click

import q2cli.util


class CLIConfig():
    path = os.path.join(q2cli.util.get_app_dir(), 'cli-colors.theme')
    VALID_SELECTORS = frozenset(
        ['option', 'type', 'default_arg', 'command', 'emphasis', 'problem',
         'warning', 'error', 'required', 'success'])
    VALID_STYLINGS = frozenset(
        ['fg', 'bg', 'bold', 'dim', 'underline', 'blink', 'reverse'])
    VALID_COLORS = frozenset(
        ['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white',
         'bright_black', 'bright_red', 'bright_green', 'bright_yellow',
         'bright_blue', 'bright_magenta', 'bright_cyan', 'bright_white'])
    VALID_BOOLEANS = {'true': True,
                      'false': False,
                      't': True,
                      'f': False}

    def __init__(self):
        if os.path.exists(self.path):
            self.styles = self.get_editable_styles()
            try:
                self.parse_file(self.path)
            except Exception as e:
                # Let's just be safe and make no attempt to use CONFIG to
                # format this text if the CONFIG is broken
                click.secho(
                    "We encountered the following error when parsing your "
                    f"theme:\n\n{str(e)}\n\nIf you want to use a custom "
                    "theme, please either import a new theme, or reset your "
                    "current theme. If you encountered this message while "
                    "importing a new theme or resetting your current theme, "
                    "ignore it.",
                    fg='red')
                self.styles = self.get_default_styles()
        else:
            self.styles = self.get_default_styles()

    def get_default_styles(self):
        return {'option': {'fg': 'blue'},
                'type': {'fg': 'green'},
                'default_arg': {'fg': 'magenta'},
                'command': {'fg': 'blue'},
                'emphasis': {'underline': True},
                'problem': {'fg': 'yellow'},
                'warning': {'fg': 'yellow', 'bold': True},
                'error': {'fg': 'red', 'bold': True},
                'required': {'underline': True},
                'success': {'fg': 'green'}}

    # This maintains the default colors while getting rid of all the default
    # styling modifiers so what the user puts in their file is all they'll see
    def get_editable_styles(self):
        return {'option': {},
                'type': {},
                'default_arg': {},
                'command': {},
                'emphasis': {},
                'problem': {},
                'warning': {},
                'error': {},
                'required': {},
                'success': {}}

    def _build_error(self, current, valid_list, valid_string):
        valids = ', '.join(valid_list)
        raise configparser.Error(f'{current!r} is not a {valid_string}. The '
                                 f'{valid_string}s are:\n{valids}')

    def parse_file(self, fp):
        if os.path.exists(fp):
            parser = configparser.ConfigParser()
            parser.read(fp)
            for selector_user in parser.sections():
                selector = selector_user.lower()
                if selector not in self.VALID_SELECTORS:
                    self._build_error(selector_user, self.VALID_SELECTORS,
                                      'valid selector')
                for styling_user in parser[selector]:
                    styling = styling_user.lower()
                    if styling not in self.VALID_STYLINGS:
                        self._build_error(styling_user, self.VALID_STYLINGS,
                                          'valid styling')
                    val_user = parser[selector][styling]
                    val = val_user.lower()
                    if styling == 'fg' or styling == 'bg':
                        if val not in self.VALID_COLORS:
                            self._build_error(val_user, self.VALID_COLORS,
                                              'valid color')
                    else:
                        if val not in self.VALID_BOOLEANS:
                            self._build_error(val_user, self.VALID_BOOLEANS,
                                              'valid boolean')
                        val = self.VALID_BOOLEANS[val]
                    self.styles[selector][styling] = val
        else:
            raise configparser.Error(f'{fp!r} is not a valid filepath.')

    def cfg_style(self, selector, text, required=False):
        kwargs = self.styles[selector]
        if required:
            kwargs = {**self.styles[selector], **self.styles['required']}
        return click.style(text, **kwargs)


CONFIG = CLIConfig()
