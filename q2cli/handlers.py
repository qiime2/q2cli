# ----------------------------------------------------------------------------
# Copyright (c) 2016-2017, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import collections

# Sentinel to avoid the situation where `None` *is* the default value.
NoDefault = collections.namedtuple('NoDefault', [])()


class ValueNotFoundException(Exception):
    """Raised when a value cannot be found. Used for control-flow only."""


class Handler:
    def __init__(self, name, prefix='', default=NoDefault, description=None):
        # e.g. my_option_name
        self.name = name
        # e.g. p_my_option_name
        self.click_name = prefix + name
        self.default = default
        self.description = description
        self.missing = []

    @property
    def cli_name(self):
        import q2cli.util

        # e.g. p-my-option-name
        return q2cli.util.to_cli_name(self.click_name)

    def get_click_options(self):
        """Should yield 1 or more click.Options"""
        raise NotImplementedError()

    def get_value(self, arguments, fallback=None):
        """Should find 1 or more arguments and convert to a single API value"""
        raise NotImplementedError()

    def _locate_value(self, arguments, fallback, multiple=False):
        """Default lookup procedure to find a click.Option provided by user"""
        # TODO revisit this interaction between _locate_value, single vs.
        # multiple options, and fallbacks. Perhaps handlers should always
        # use tuples to store values, even for single options, in order to
        # normalize single-vs-multiple option handling. Probably not worth
        # revisiting until there are more unit + integration tests of q2cli
        # since there's the potential to break things.

        # Is it in args?
        v = arguments[self.click_name]
        missing_value = () if multiple else None
        if v != missing_value:
            return v

        # Does our fallback know about it?
        if fallback is not None:
            try:
                fallback_value = fallback(self.name, self.cli_name)
            except ValueNotFoundException:
                pass
            else:
                # TODO fallbacks don't know whether they're handling a single
                # vs. multiple option, so the current expectation is that
                # fallbacks will always return a single value. Revisit this
                # expectation in the future; perhaps fallbacks should be aware
                # of single-vs-multiple options, or perhaps they could always
                # return a tuple.
                if multiple:
                    fallback_value = (fallback_value,)
                return fallback_value

        # Do we have a default?
        if self.default is not NoDefault:
            return self.default

        # Give up
        self.missing.append(self.cli_name)
        raise ValueNotFoundException()

    def _parse_boolean(self, string):
        """Parse string representing a boolean into Python bool type.

        Supported values match `configparser.ConfigParser.getboolean`.

        """
        trues = ['1', 'yes', 'true', 'on']
        falses = ['0', 'no', 'false', 'off']

        string_lower = string.lower()
        if string_lower in trues:
            return True
        elif string_lower in falses:
            return False
        else:
            import itertools
            import click

            msg = (
                "Error: unrecognized value for --%s flag: %s\n"
                "Supported values (case-insensitive): %s" %
                (self.cli_name, string,
                 ', '.join(itertools.chain(trues, falses)))
            )
            click.secho(msg, err=True, fg='red', bold=True)
            ctx = click.get_current_context()
            ctx.exit(1)

    def _add_description(self, option, requirement):
        def pretty_cat(a, b, space=1):
            if a:
                return a + (' ' * space) + b
            return b

        if self.description:
            option.help = pretty_cat(option.help, self.description)
        option.help = pretty_cat(option.help, requirement, space=2)

        return option


class VerboseHandler(Handler):
    """Handler for verbose output (--verbose flag)."""

    def __init__(self):
        super().__init__('verbose', default=False)

    def get_click_options(self):
        import q2cli

        # `is_flag` will set the default to `False`, but `self._locate_value`
        # needs to distinguish between the presence or absence of the flag
        # provided by the user.
        yield q2cli.Option(
            ['--' + self.cli_name], is_flag=True, default=None,
            help='Display verbose output to stdout and/or stderr during '
                 'execution of this action.  [default: %s]' % self.default)

    def get_value(self, arguments, fallback=None):
        value = self._locate_value(arguments, fallback)
        # Value may have been specified in --cmd-config (or another source in
        # the future). If we don't have a bool type yet, attempt to interpret a
        # string representing a boolean.
        if type(value) is not bool:
            value = self._parse_boolean(value)
        return value


class QuietHandler(Handler):
    """Handler for quiet output (--quiet flag)."""

    def __init__(self):
        super().__init__('quiet', default=False)

    def get_click_options(self):
        import q2cli

        # `is_flag` will set the default to `False`, but `self._locate_value`
        # needs to distinguish between the presence or absence of the flag
        # provided by the user.
        yield q2cli.Option(
            ['--' + self.cli_name], is_flag=True, default=None,
            help='Silence output if execution is successful '
                 '(silence is golden).  [default: %s]' % self.default)

    def get_value(self, arguments, fallback=None):
        value = self._locate_value(arguments, fallback)
        # Value may have been specified in --cmd-config (or another source in
        # the future). If we don't have a bool type yet, attempt to interpret a
        # string representing a boolean.
        if type(value) is not bool:
            value = self._parse_boolean(value)
        return value


class OutputDirHandler(Handler):
    """Meta handler which returns a fallback function as its value."""

    def __init__(self):
        super().__init__('output_dir')

    def get_click_options(self):
        import click
        import q2cli

        yield q2cli.Option(
            ['--' + self.cli_name],
            type=click.Path(exists=False, dir_okay=True, file_okay=False,
                            writable=True),
            help='Output unspecified results to a directory')

    def get_value(self, arguments, fallback=None):
        import os
        import os.path
        import click

        try:
            path = self._locate_value(arguments, fallback=fallback)

            # TODO: do we want a --force like flag?
            if os.path.exists(path):
                click.secho("Error: --%s directory already exists, won't "
                            "overwrite." % self.cli_name, err=True, fg='red',
                            bold=True)
                ctx = click.get_current_context()
                ctx.exit(1)

            os.makedirs(path)

            def fallback_(name, cli_name):
                return os.path.join(path, name)
            return fallback_

        except ValueNotFoundException:
            # Always fail to find a value as this handler doesn't exist.
            def fail(*_):
                raise ValueNotFoundException()

            return fail


class CommandConfigHandler(Handler):
    """Meta handler which returns a fallback function as its value."""

    def __init__(self, cli_plugin, cli_action):
        self.cli_plugin = cli_plugin
        self.cli_action = cli_action
        super().__init__('cmd_config')

    def get_click_options(self):
        import click
        import q2cli

        yield q2cli.Option(
            ['--' + self.cli_name],
            type=click.Path(exists=True, dir_okay=False, file_okay=True,
                            readable=True),
            help='Use config file for command options')

    def get_value(self, arguments, fallback=None):
        import configparser
        import warnings

        try:
            path = self._locate_value(arguments, fallback=fallback)
            config = configparser.ConfigParser()
            config.read(path)
            try:
                config_section = config['.'.join([
                    self.cli_plugin, self.cli_action
                ])]
            except KeyError:
                warnings.warn("Config file does not contain a section"
                              " for %s"
                              % '.'.join([self.cli_plugin, self.cli_action]),
                              UserWarning)
                raise ValueNotFoundException()

            def fallback_(name, cli_name):
                try:
                    return config_section[cli_name]
                except KeyError:
                    raise ValueNotFoundException()
            return fallback_

        except ValueNotFoundException:
            # Always fail to find a value as this handler doesn't exist.
            def fail(*_):
                raise ValueNotFoundException()

            return fail


class GeneratedHandler(Handler):
    def __init__(self, name, repr, ast, default=NoDefault, description=None):
        super().__init__(name, prefix=self.prefix, default=default,
                         description=description)
        self.repr = repr
        self.ast = ast


class CollectionHandler(GeneratedHandler):
    view_map = {
        'List': list,
        'Set': set
    }

    def __init__(self, inner_handler, **kwargs):
        self.inner_handler = inner_handler
        # inner_handler needs to be set first so the prefix lookup works
        super().__init__(**kwargs)
        self.view_type = self.view_map[self.ast['name']]

    @property
    def prefix(self):
        return self.inner_handler.prefix

    def get_click_options(self):
        import q2cli.core
        for option in self.inner_handler.get_click_options():
            option.multiple = True
            # validation happens on a callback for q2cli.core.Option, so unset
            # it because we need standard click behavior for multi-options
            # without this, the result of not-passing a value is `None` instead
            # of `()` which confuses ._locate_value
            option.callback = None
            option.type = q2cli.core.MultipleType(option.type)
            yield option

    def get_value(self, arguments, fallback=None):
        args = self._locate_value(arguments, fallback, multiple=True)
        if args is None:
            return None

        decoded_values = []
        for arg in args:
            # Use an empty dict because we don't need the inner handler to
            # look for anything; that's our job. We just need it to decode
            # whatever it was we found.
            empty = collections.defaultdict(lambda: None)
            decoded = self.inner_handler.get_value(empty,
                                                   fallback=lambda *_: arg)
            decoded_values.append(decoded)

        value = self.view_type(decoded_values)

        if len(value) != len(decoded_values):
            self._error_with_duplicate_in_set(decoded_values)

        return value

    def _error_with_duplicate_in_set(self, elements):
        import click
        import collections

        counter = collections.Counter(elements)
        dups = {name for name, count in counter.items() if count > 1}

        ctx = click.get_current_context()
        click.echo(ctx.get_usage() + '\n', err=True)
        click.secho("Error: Option --%s was given these values: %r more than "
                    "one time, values passed should be unique."
                    % (self.cli_name, dups), err=True, fg='red', bold=True)
        ctx.exit(1)


class ArtifactHandler(GeneratedHandler):
    prefix = 'i_'

    def get_click_options(self):
        import q2cli
        import q2cli.core

        type = q2cli.core.ResultPath(repr=self.repr, exists=True,
                                     file_okay=True, dir_okay=False,
                                     readable=True)
        if self.default is None:
            requirement = '[optional]'
        else:
            requirement = '[required]'

        option = q2cli.Option(['--' + self.cli_name], type=type, help="")
        yield self._add_description(option, requirement)

    def get_value(self, arguments, fallback=None):
        import qiime2

        path = self._locate_value(arguments, fallback)
        if path is None:
            return None
        else:
            return qiime2.Artifact.load(path)


class ResultHandler(GeneratedHandler):
    prefix = 'o_'

    def get_click_options(self):
        import q2cli

        type = q2cli.core.ResultPath(self.repr, exists=False, file_okay=True,
                                     dir_okay=False, writable=True)
        option = q2cli.Option(['--' + self.cli_name], type=type, help="")
        yield self._add_description(
            option, '[required if not passing --output-dir]')

    def get_value(self, arguments, fallback=None):
        return self._locate_value(arguments, fallback)


def parameter_handler_factory(name, repr, ast, default=NoDefault,
                              description=None):
    if ast['name'] == 'Metadata':
        return MetadataHandler(name, default=default, description=description)
    elif ast['name'] == 'MetadataCategory':
        return MetadataCategoryHandler(name, default=default,
                                       description=description)
    else:
        return RegularParameterHandler(name, repr, ast, default=default,
                                       description=description)


class MetadataHandler(Handler):
    def __init__(self, name, default=NoDefault, description=None):
        if default is not NoDefault and default is not None:
            raise TypeError(
                "The only supported default value for Metadata is `None`. "
                "Found this default value: %r" % (default,))

        super().__init__(name, prefix='m_', default=default,
                         description=description)
        self.click_name += '_file'

    def get_click_options(self):
        import click
        import q2cli
        import q2cli.core

        name = '--' + self.cli_name
        type = click.Path(exists=True, file_okay=True, dir_okay=False,
                          readable=True)
        type = q2cli.core.MultipleType(type)
        help = ('Metadata file or artifact viewable as metadata. This '
                'option may be supplied multiple times to merge metadata.')

        if self.default is None:
            requirement = '[optional]'
        else:
            requirement = '[required]'

        option = q2cli.Option([name], type=type, help=help, multiple=True)
        yield self._add_description(option, requirement)

    def get_value(self, arguments, fallback=None):
        import os
        import qiime2
        import q2cli.util

        paths = self._locate_value(arguments, fallback, multiple=True)
        if paths is None:
            return paths

        metadata = []
        for path in paths:
            try:
                # check to see if path is an artifact
                artifact = qiime2.Artifact.load(path)
            except Exception:
                try:
                    metadata.append(qiime2.Metadata.load(path))
                except Exception as e:
                    header = ("There was an issue with loading the file %s as "
                              "metadata:" % path)
                    with open(os.devnull, 'w') as dev_null:
                        q2cli.util.exit_with_error(
                            e, header=header, file=dev_null,
                            suppress_footer=True)
            else:
                try:
                    metadata.append(qiime2.Metadata.from_artifact(artifact))
                except Exception as e:
                    header = ("There was an issue with viewing the artifact "
                              "%s as metadata:" % path)
                    with open(os.devnull, 'w') as dev_null:
                        q2cli.util.exit_with_error(
                            e, header=header, file=dev_null,
                            suppress_footer=True)
        return metadata[0].merge(*metadata[1:])


class MetadataCategoryHandler(Handler):
    def __init__(self, name, default=NoDefault, description=None):
        if default is not NoDefault and default is not None:
            raise TypeError(
                "The only supported default value for MetadataCategory is "
                "`None`. Found this default value: %r" % (default,))

        super().__init__(name, prefix='m_', default=default,
                         description=description)
        self.click_name += '_category'

        # Not passing `description` to metadata handler because `description`
        # applies to the metadata category (`self`).
        self.metadata_handler = MetadataHandler(name, default=default)

    def get_click_options(self):
        import q2cli

        name = '--' + self.cli_name
        type = str
        help = ('Category from metadata file or artifact viewable as '
                'metadata.')

        if self.default is None:
            requirement = '[optional]'
        else:
            requirement = '[required]'

        option = q2cli.Option([name], type=type, help=help)

        yield from self.metadata_handler.get_click_options()
        yield self._add_description(option, requirement)

    def get_value(self, arguments, fallback=None):
        # Attempt to find all options before erroring so that all handlers'
        # missing options can be displayed to the user.
        try:
            metadata_value = self.metadata_handler.get_value(arguments,
                                                             fallback=fallback)
        except ValueNotFoundException:
            pass

        try:
            category_value = self._locate_value(arguments, fallback)
        except ValueNotFoundException:
            pass

        missing = self.metadata_handler.missing + self.missing
        if missing:
            self.missing = missing
            raise ValueNotFoundException()

        # If metadata category is optional, there is a chance for metadata to
        # be provided without a metadata category, or vice versa.
        if metadata_value is None and category_value is not None:
            self.missing.append(self.metadata_handler.cli_name)
            raise ValueNotFoundException()
        elif metadata_value is not None and category_value is None:
            self.missing.append(self.cli_name)
            raise ValueNotFoundException()

        if metadata_value is None and category_value is None:
            return None
        else:
            return metadata_value.get_category(category_value)


class RegularParameterHandler(GeneratedHandler):
    prefix = 'p_'

    def __init__(self, name, repr, ast, default=NoDefault, description=None):
        import q2cli.util

        super().__init__(name, repr, ast, default=default,
                         description=description)
        # TODO: just create custom click.ParamType to avoid this silliness
        if ast['type'] == 'collection':
            ast, = ast['fields']
        self.type = q2cli.util.convert_primitive(ast)

    def get_click_options(self):
        import q2cli
        import q2cli.util

        if self.type is bool:
            no_name = self.prefix + 'no_' + self.name
            cli_no_name = q2cli.util.to_cli_name(no_name)
            name = '--' + self.cli_name + '/--' + cli_no_name
            # click.Option type is determined implicitly for flags with
            # secondary options, and explicitly passing type=bool results in a
            # TypeError, so we pass type=None (the default).
            option_type = None
        else:
            name = '--' + self.cli_name
            option_type = self.type

        if self.default is NoDefault:
            requirement = '[required]'
        elif self.default is None:
            requirement = '[optional]'
        else:
            requirement = '[default: %s]' % self.default

        # Pass `default=None` and `show_default=False` to `click.Option`
        # because the handlers are responsible for resolving missing values and
        # supplying defaults. Telling Click about the default value here makes
        # it impossible to determine whether the user supplied or omitted a
        # value once the handlers are invoked.
        option = q2cli.Option([name], type=option_type, default=None,
                              show_default=False, help='')

        yield self._add_description(option, requirement)

    def get_value(self, arguments, fallback=None):
        value = self._locate_value(arguments, fallback)
        if value is None:
            return None

        elif self.type is bool:
            # TODO: should we defer to the Bool primitive? It only allows
            # 'true' and 'false'.
            if type(value) is not bool:
                value = self._parse_boolean(value)
            return value
        else:
            import qiime2.sdk
            primitive = qiime2.sdk.parse_type(self.repr, expect='primitive')
            # TODO/HACK: the repr is the primitive used, but since there's a
            # collection handler managing the set/list this get_value should
            # handle only the pieces. This is super gross, but would be
            # unecessary if click.ParamTypes were implemented for each
            # kind of QIIME 2 input.
            if self.ast['type'] == 'collection':
                primitive, = primitive.fields

            return primitive.decode(value)
