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
    VALID_SELECTORS = {'option', 'type', 'default_arg', 'command', 'emphasis',
                       'problem', 'error', 'required', 'success'}
    VALID_STYLINGS = {'fg', 'bg', 'bold', 'dim', 'underline', 'blink',
                      'reverse'}
    VALID_COLORS = {'black', 'red', 'green', 'yellow', 'blue', 'magenta',
                    'cyan', 'white', 'bright_black', 'bright_red',
                    'bright_green', 'bright_yellow', 'bright_blue',
                    'bright_magenta', 'bright_cyan', 'bright_white'}
    VALID_BOOLEANS = {'true': True,
                      'false': False,
                      't': True,
                      'f': False}

    def __init__(self):
        self.styles = self._get_default_styles()
        try:
            self.parse_file(self.path)
        except Exception:
            if os.path.exists(self.path):
                os.unlink(self.path)
            self.styles = self._get_default_styles()

    def _get_default_styles(self):
        return {'option': {'fg': 'blue'},
                'type': {'fg': 'green'},
                'default_arg': {'fg': 'magenta'},
                'command': {'fg': 'blue'},
                'emphasis': {'underline': True},
                'problem': {'fg': 'yellow'},
                'error': {'fg': 'red', 'bold': True},
                'required': {'underline': True},
                'success': {'fg': 'green'}}

    def _build_error(self, current, valid_list, valid_string):
        valids = ''
        for valid in valid_list:
            valids += valid + '\n'
        raise ValueError(f'{current!r} is not a {valid_string}. The '
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
            # If the bad path is the default path they don't have a custom
            # config. If the bad path isn't the default path they tried to
            # import a nonexistent file and we want to error
            if fp != self.path:
                raise ValueError(f'{fp!r} is not a valid filepath.')

    def cfg_style(self, selector, text, required=False):
        kwargs = self.styles[selector]
        if required:
            kwargs = {**self.styles[selector], **self.styles['required']}
        return click.style(text, **kwargs)


CONFIG = CLIConfig()
