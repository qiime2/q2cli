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


class cli_config():
    path = os.path.join(q2cli.util.get_app_dir(), 'cli-colors.theme')
    valid_types = ['options', 'type', 'default_arg', 'command', 'emphasis',
                   'problem', 'errors', 'required', 'success']
    valid_stylings = ['fg', 'bg', 'bold', 'dim', 'underline', 'blink',
                      'reverse']
    valid_colors = ['black', 'red', 'green', 'yellow', 'blue', 'magenta',
                    'cyan', 'white', 'bright_black', 'bright_red',
                    'bright_green', 'bright_yellow', 'bright_blue',
                    'bright_magenta', 'bright_cyan', 'bright_white']
    valid_booleans = {'true': True,
                      'false': False,
                      't': True,
                      'f': False}
    styles = {'options': {'fg': 'blue'},
              'type': {'fg': 'green'},
              'default_args': {'fg': 'magenta'},
              'command': {'fg': 'blue'},
              'emphasis': {'underline': True},
              'problem': {'fg': 'yellow'},
              'errors': {'fg': 'red', 'bold': True},
              'required': {'underline': True},
              'success': {'fg': 'green'}}

    def __init__(self):
        self.parse_file()

    def build_error(self, current, valid_list, valid_string):
        valids = ''
        for valid in valid_list:
            valids += valid + '\n'
        raise ValueError(f'{current!r} is not a {valid_string}. The '
                         f'{valid_string}s are:\n{valids}')

    def parse_file(self, fp=path):
        try:
            if os.path.exists(fp):
                parser = configparser.ConfigParser()
                parser.read(fp)
                for type_user in parser.sections():
                    type = type_user.lower()
                    if type not in self.valid_types:
                        self.build_error(type_user, self.valid_types,
                                         'valid type')
                    for styling_user in parser[type]:
                        styling = styling_user.lower()
                        if styling not in self.valid_stylings:
                            self.build_error(styling_user, self.valid_stylings,
                                             'valid styling')
                        val_user = parser[type][styling]
                        val = val_user.lower()
                        if styling == 'fg' or styling == 'bg':
                            if val not in self.valid_colors:
                                self.build_error(val_user, self.valid_colors,
                                                 'valid color')
                        else:
                            if val not in self.valid_booleans:
                                self.build_error(val_user, self.valid_booleans,
                                                 'valid boolean')
                            val = self.valid_booleans[val]
                        self.styles[type][styling] = val
            else:
                # If the bad path is the default path they don't have a custom
                # config. If the bad path isn't the default path they tried to
                # import a nonexistent file and we want to error
                if fp != self.path:
                    raise ValueError(f'{fp!r} is not a valid filepath.')
        except Exception as e:
            if os.path.exists(fp):
                os.unlink(fp)
            raise e

    def cfg_style(self, type, text, required=False):
        reqs = {}
        kwargs = self.styles[type]
        if required:
            reqs = self.styles['required']
        for req in reqs:
            if req in kwargs:
                kwargs.pop(req)
        return click.style(text, **kwargs, **reqs)


CONFIG = cli_config()
