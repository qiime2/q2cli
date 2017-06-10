# ----------------------------------------------------------------------------
# Copyright (c) 2016-2017, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import collections

# TODO: revisit how default values are handled when optional artifacts are
# supported.

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

    def _locate_value(self, arguments, fallback, name=None, click_name=None,
                      cli_name=None):
        """Default lookup procedure to find a click.Option provided by user"""
        if name is None:
            name = self.name
        if click_name is None:
            click_name = self.click_name
        if cli_name is None:
            cli_name = self.cli_name

        # Is it in args?
        v = arguments[click_name]
        if v is not None:
            return v

        # Does our fallback know about it?
        if fallback is not None:
            try:
                return fallback(name, cli_name)
            except ValueNotFoundException:
                pass

        # Do we have a default?
        if self.default is not NoDefault:
            return self.default

        # Give up
        self.missing.append(cli_name)
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

    def _add_description(self, option):
        if self.description:
            option.help += '\n%s' % self.description
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
            type=click.Path(exists=False, dir_okay=True, file_okay=False),
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
    def __init__(self, name, repr, default=NoDefault, description=None):
        super().__init__(name, prefix=self.prefix, default=default,
                         description=description)
        self.repr = repr


class ArtifactHandler(GeneratedHandler):
    prefix = 'i_'

    def get_click_options(self):
        import click
        import q2cli

        option = q2cli.Option(['--' + self.cli_name],
                              type=click.Path(exists=False, dir_okay=False),
                              help="Artifact: %s  [required]" % self.repr)
        yield self._add_description(option)

    def get_value(self, arguments, fallback=None):
        import qiime2

        path = self._locate_value(arguments, fallback)
        return qiime2.Artifact.load(path)


class ResultHandler(GeneratedHandler):
    prefix = 'o_'

    def get_click_options(self):
        import click
        import q2cli

        option = q2cli.Option(['--' + self.cli_name],
                              type=click.Path(exists=False, dir_okay=False),
                              help="Artifact: %s  [required if not passing "
                              "--output-dir]" % self.repr)
        yield self._add_description(option)

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
        super().__init__(name, prefix='m_', default=default,
                         description=description)
        self.click_name += '_file'

    def get_click_options(self):
        import click
        import q2cli

        name = '--' + self.cli_name
        type = click.Path(exists=True, dir_okay=False)
        help = 'Metadata mapping file'

        # Metadata currently supports a default of None. Anything else makes it
        # required.
        option = None
        if self.default is None:
            option = q2cli.Option([name], type=type,
                                  help='%s  [optional]' % help)
        else:
            option = q2cli.Option([name], type=type,
                                  help='%s  [required]' % help)

        yield self._add_description(option)

    def get_value(self, arguments, fallback=None):
        import qiime2

        path = self._locate_value(arguments, fallback)
        if path is None:
            return None
        try:
            # check to see if path is an artifact
            artifact = qiime2.Artifact.load(path)
        except Exception:
            pass
        else:
            if artifact.has_metadata():
                return qiime2.Metadata.from_artifact(artifact)
            else:
                raise ValueError("Artifact (%s) has no metadata." % path)

        return qiime2.Metadata.load(path)


class MetadataCategoryHandler(Handler):
    def __init__(self, name, default=NoDefault, description=None):
        import q2cli.util

        super().__init__(name, prefix='m_', default=default,
                         description=description)
        self.name = name
        self.click_names = ['m_%s_file' % name, 'm_%s_category' % name]
        self.cli_names = [
            q2cli.util.to_cli_name(n) for n in self.click_names]

    def get_click_options(self):
        import click
        import q2cli

        md_name = '--' + self.cli_names[0]
        md_help = 'Metadata mapping file'
        md_kwargs = {
            'type': click.Path(exists=True, dir_okay=False)
        }

        mdc_name = '--' + self.cli_names[1]
        mdc_help = 'Category from metadata mapping file'
        mdc_kwargs = {
            'type': str
        }

        # Metadata currently supports a default of None. Anything else makes it
        # required.
        if self.default is None:
            md_kwargs['help'] = '%s  [optional]' % md_help
            mdc_kwargs['help'] = '%s  [optional]' % mdc_help
        else:
            md_kwargs['help'] = '%s  [required]' % md_help
            mdc_kwargs['help'] = '%s  [required]' % mdc_help

        yield q2cli.Option([md_name], **md_kwargs)
        yield q2cli.Option([mdc_name], **mdc_kwargs)

    def get_value(self, arguments, fallback=None):
        import qiime2

        values = []
        failed = False
        # This is nastier looking than it really is.
        # Just try to locate both values and handle failure.
        # `_locate_value` automatically append to `self.missing` when it fails
        for click_name, cli_name in zip(self.click_names, self.cli_names):
            try:
                value = self._locate_value(arguments, fallback,
                                           click_name=click_name,
                                           cli_name=cli_name)
                values.append(value)
            except ValueNotFoundException:
                failed = True

        if failed:
            raise ValueNotFoundException()
        if values == [None, None]:
            return None

        path, category = values
        try:
            # check to see if path is an artifact
            artifact = qiime2.Artifact.load(path)
        except Exception:
            pass
        else:
            if artifact.has_metadata():
                return qiime2.MetadataCategory.from_artifact(artifact,
                                                             category)
            else:
                raise ValueError("Artifact (%s) has no metadata." % path)

        return qiime2.MetadataCategory.load(*values)


class RegularParameterHandler(GeneratedHandler):
    prefix = 'p_'

    def __init__(self, name, repr, ast, default=NoDefault, description=None):
        super().__init__(name, repr, default=default, description=description)
        self.ast = ast

    def get_type(self):
        import click

        mapping = {
            'Int': int,
            'Str': str,
            'Float': float,
            'Color': str,
            'Bool': bool
        }
        # TODO: This is a hack because we only support a few predicates at
        # this point. This entire class should be revisited at some point.
        predicate = self.ast['predicate']
        if predicate:
            if predicate['name'] == 'Choices' and self.ast['name'] == 'Str':
                return click.Choice(predicate['choices'])
            elif predicate['name'] == 'Range' and self.ast['name'] == 'Int':
                start = predicate['start']
                end = predicate['end']
                # click.IntRange is always inclusive
                if start is not None and not predicate['inclusive-start']:
                    start += 1
                if end is not None and not predicate['inclusive-end']:
                    end -= 1
                return click.IntRange(start, end)
            elif predicate['name'] == 'Range' and self.ast['name'] == 'Float':
                # click.FloatRange will be in click 7.0, so for now the
                # range handling will just fallback to qiime2.
                return mapping['Float']
            else:
                raise NotImplementedError()
        return mapping[self.ast['name']]

    def get_click_options(self):
        import q2cli
        import q2cli.util

        type = self.get_type()  # Use the ugly lookup above
        if type is bool:
            no_name = self.prefix + 'no_' + self.name
            cli_no_name = q2cli.util.to_cli_name(no_name)
            name = '--' + self.cli_name + '/--' + cli_no_name
            # click.Option type is determined implicitly for flags with
            # secondary options, and explicitly passing type=bool results in a
            # TypeError, so we pass type=None (the default).
            option_type = None
        else:
            name = '--' + self.cli_name
            option_type = type

        # Pass `default=None` and `show_default=False` to `click.Option`
        # because the handlers are responsible for resolving missing values and
        # supplying defaults. Telling Click about the default value here makes
        # it impossible to determine whether the user supplied or omitted a
        # value once the handlers are invoked.
        option = None
        if self.default is NoDefault:
            option = q2cli.Option([name], type=option_type, default=None,
                                  show_default=False, help='[required]')
        elif self.default is None:
            option = q2cli.Option([name], type=option_type, default=None,
                                  show_default=False, help='[optional]')
        else:
            option = q2cli.Option([name], type=option_type, default=None,
                                  show_default=False,
                                  help='[default: %s]' % self.default)

        yield self._add_description(option)

    def get_value(self, arguments, fallback=None):
        value = self._locate_value(arguments, fallback)
        if value is None:
            return None
        elif self.get_type() is bool:
            # Value may have been specified in --cmd-config (or another source
            # in the future). If we don't have a bool type yet, attempt to
            # interpret a string representing a boolean.
            if type(value) is not bool:
                value = self._parse_boolean(value)
            return value
        else:
            import qiime2.sdk
            return qiime2.sdk.parse_type(
                self.repr, expect='primitive').decode(value)
