# ----------------------------------------------------------------------------
# Copyright (c) 2016--, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------
import os
import collections
import configparser
import warnings

import click
import qiime

import q2cli.util

# Sentinel to avoid the situation where `None` *is* the default value.
NoDefault = collections.namedtuple('NoDefault', [])()


class ValueNotFoundException(Exception):
    """Raised when a value cannot be found. Used for control-flow only."""


class Handler:
    def __init__(self, name, prefix='', default=NoDefault):
        # e.g. my_option_name
        self.name = name
        # e.g. p_my_option_name
        self.click_name = prefix + name
        self.default = default
        self.missing = []

    @property
    def cli_name(self):
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


class OutputDirHandler(Handler):
    """Meta handler which returns a fallback function as its value."""

    def __init__(self):
        super().__init__('output_dir')

    def get_click_options(self):
        yield click.Option(
            ['--' + self.cli_name],
            type=click.Path(exists=False, dir_okay=True, file_okay=False),
            help='Output unspecified results to a directory')

    def get_value(self, arguments, fallback=None):
        try:
            path = self._locate_value(arguments, fallback=fallback)
            # TODO: do we want a --force like flag?
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
        yield click.Option(
            ['--' + self.cli_name],
            type=click.Path(exists=True, dir_okay=False, file_okay=True,
                            readable=True),
            help='Use config file for command options')

    def get_value(self, arguments, fallback=None):
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
    def __init__(self, name, semtype, default=NoDefault):
        super().__init__(name, prefix=self.prefix, default=default)
        self.semtype = semtype
        self.ast = semtype.to_ast()


class ArtifactHandler(GeneratedHandler):
    prefix = 'i_'

    def get_click_options(self):
        yield click.Option(['--' + self.cli_name],
                           type=click.Path(exists=False, dir_okay=False),
                           help="Input %r" % self.semtype)

    def get_value(self, arguments, fallback=None):
        path = self._locate_value(arguments, fallback)

        return qiime.Artifact.load(path)


class ResultHandler(GeneratedHandler):
    prefix = 'o_'

    def get_click_options(self):
        yield click.Option(['--' + self.cli_name],
                           type=click.Path(exists=False, dir_okay=False),
                           help="Output %r" % self.semtype)

    def get_value(self, arguments, fallback=None):
        return self._locate_value(arguments, fallback)


def parameter_handler_factory(name, semtype, default=NoDefault):
    ast = semtype.to_ast()
    if ast['name'] == 'Metadata':
        return MetadataHandler(name)
    elif ast['name'] == 'MetadataCategory':
        return MetadataCategoryHandler(name)
    return RegularParameterHandler(name, semtype, default=default)


class MetadataHandler(Handler):
    def __init__(self, name):
        super().__init__(name, prefix='m_')
        self.click_name += '_file'

    def get_click_options(self):
        yield click.Option(['--' + self.cli_name],
                           type=click.Path(exists=True, dir_okay=False),
                           help='Metadata mapping file')

    def get_value(self, arguments, fallback=None):
        path = self._locate_value(arguments, fallback)
        return qiime.Metadata.load(path)


class MetadataCategoryHandler(Handler):
    def __init__(self, name):
        super().__init__(name, prefix='m_')
        self.name = name
        self.click_names = ['m_%s_file' % name, 'm_%s_category' % name]
        self.cli_names = [
            q2cli.util.to_cli_name(n) for n in self.click_names]

    def get_click_options(self):
        yield click.Option(['--' + self.cli_names[0]],
                           type=click.Path(exists=True, dir_okay=False),
                           help='Metadata mapping file')

        yield click.Option(['--' + self.cli_names[1]],
                           type=str,
                           help='Category from metadata mapping file')

    def get_value(self, arguments, fallback=None):
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

        return qiime.MetadataCategory.load(*values)


class RegularParameterHandler(GeneratedHandler):
    prefix = 'p_'

    def get_type(self):
        mapping = {
            'Int': int,
            'Str': str,
            'Float': float,
            'Color': str,
            'Bool': bool
        }
        # TODO: This is a hack because we only support Str % Choices(...) at
        # this point. This entire class should be revisited at some point.
        predicate = self.ast['predicate']
        if predicate:
            if predicate['name'] != 'Choices' and self.ast['name'] != 'Str':
                raise NotImplementedError()
            return click.Choice(predicate['choices'])
        return mapping[self.ast['name']]

    def get_click_options(self):
        type = self.get_type()  # Use the ugly lookup above
        if type is bool:
            no_name = self.prefix + 'no_' + self.name
            cli_no_name = q2cli.util.to_cli_name(no_name)
            yield click.Option(['--' + self.cli_name + '/--' + cli_no_name])
        else:
            yield click.Option(['--' + self.cli_name], type=type)

    def get_value(self, arguments, fallback=None):
        value = self._locate_value(arguments, fallback)
        if self.get_type() is bool:
            value = self.semtype.encode(value)
        return self.semtype.decode(value)
