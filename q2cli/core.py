# ----------------------------------------------------------------------------
# Copyright (c) 2016-2019, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import click

import q2cli.util


class Option(click.Option):
    """``click.Option`` with customized behavior for q2cli.

    Note to q2cli developers: you'll generally want to use this class and its
    corresponding decorator (``@q2cli.option``) over ``click.Option`` and
    ``@click.option`` to keep a consistent CLI behavior across commands. This
    class and decorator are designed to be drop-in replacements for their Click
    counterparts.

    """
    def __init__(self, param_decls=None, **attrs):
        super().__init__(param_decls=param_decls, **attrs)


# Modeled after `click.option` decorator.
def option(*param_decls, **attrs):
    """``@click.option`` decorator with customized behavior for q2cli.

    See docstring on ``q2cli.Option`` (above) for details.

    """
    if 'cls' in attrs:
        raise ValueError("Cannot override `cls=q2cli.Option` in `attrs`.")
    attrs['cls'] = Option

    def decorator(f):
        return click.option(*param_decls, **attrs)(f)

    return decorator


class MultipleType(click.ParamType):
    """This is just a wrapper, it doesn't do anything on its own"""
    def __init__(self, param_type):
        self.param_type = param_type

    @property
    def name(self):
        return "MULTIPLE " + self.param_type.name

    def convert(self, value, param, ctx):
        # Don't convert anything yet.
        return value

    def fail(self, *args, **kwargs):
        return self.param_type.fail(*args, **kwargs)

    def get_missing_message(self, *args, **kwargs):
        return self.param_type.get_missing_message(*args, **kwargs)

    def get_metavar(self, *args, **kwargs):
        metavar = self.param_type.get_metavar(*args, **kwargs)
        if metavar is None:
            return None
        return "MULTIPLE " + metavar


class ResultPath(click.Path):
    def __init__(self, repr, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.repr = repr

    def get_metavar(self, param):
        if self.repr != 'Visualization':
            return "ARTIFACT " + click.style(self.repr, fg='green')
        return "VISUALIZATION"
