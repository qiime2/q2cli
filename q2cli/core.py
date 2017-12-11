# ----------------------------------------------------------------------------
# Copyright (c) 2016-2017, QIIME 2 development team.
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
        if 'multiple' not in attrs and 'count' not in attrs:
            self._disallow_repeated_options(attrs)
        super().__init__(param_decls=param_decls, **attrs)

    def _disallow_repeated_options(self, attrs):
        """Prevent option from being repeated on the command line.

        Click allows options to be repeated on the command line and stores the
        value of the last specified option (this is to support overriding
        options set in shell aliases). While this is common behavior in CLI
        tools, it is prevented in q2cli to avoid confusion with options that
        are intended to be supplied multiple times (``multiple=True``; Click
        calls these "multiple options"). QIIME 2 metadata is an example of a
        "multiple option" in q2cli.

        References
        ----------
        .. [1] http://click.pocoo.org/6/options/#multiple-options

        """
        # General strategy:
        #
        # Make this option a "multiple option" (``multiple=True``) and use a
        # callback to unpack the stored values and assert that only a single
        # value was supplied.

        # Use the user-supplied callback or define a passthrough callback if
        # one wasn't supplied.
        if 'callback' in attrs:
            callback = attrs['callback']
        else:
            def callback(ctx, param, value):
                return value

        # Wrap the callback to intercept stored values so that they can be
        # unpacked and validated.
        def callback_wrapper(ctx, param, value):
            # When `multiple=True` Click will use an empty tuple to represent
            # the absence of the option instead of `None`.
            if value == ():
                value = None
            if not value or ctx.resilient_parsing:
                return callback(ctx, param, value)

            # Empty/null case is handled above, so attempt to unpack the value.
            try:
                value, = value
            except ValueError:
                click.echo(ctx.get_usage() + '\n', err=True)
                click.secho(
                    "Error: Option --%s was specified multiple times in the "
                    "command." % q2cli.util.to_cli_name(param.name),
                    err=True, fg='red', bold=True)
                ctx.exit(1)

            return callback(ctx, param, value)

        # Promote this option to a "multiple option" and use the callback
        # wrapper to make it behave like a regular "single" option.
        attrs['callback'] = callback_wrapper
        attrs['multiple'] = True

        # If the user set a default, promote it to a "multiple option" default
        # by putting it in a list. A default of `None` is a special case that
        # can't be promoted.
        if 'default' in attrs and attrs['default'] is not None:
            attrs['default'] = [attrs['default']]


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
            return "ARTIFACT PATH " + self.repr
        return "VISUALIZATION PATH"
