# ----------------------------------------------------------------------------
# Copyright (c) 2016-2022, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import click

from .type import QIIME2Type

# Sentinel to avoid the situation where `None` *is* the default value.
NoDefault = {}


class GeneratedOption(click.Option):
    def __init__(self, *, prefix, name, repr, ast, multiple, is_bool_flag,
                 metadata, metavar, default=NoDefault, description=None,
                 **attrs):
        import q2cli.util

        if metadata is not None:
            prefix = 'm'
        if multiple is not None:
            if multiple == 'list':
                multiple = list
            elif multiple == 'dict':
                multiple = dict
            else:
                multiple = set

        if is_bool_flag:
            yes = q2cli.util.to_cli_name(name)
            no = q2cli.util.to_cli_name('no_' + name)
            opt = f'--{prefix}-{yes}/--{prefix}-{no}'
        elif metadata is not None:
            cli_name = q2cli.util.to_cli_name(name)
            opt = f'--{prefix}-{cli_name}-file'
            if metadata == 'column':
                self.q2_extra_dest, self.q2_extra_opts, _ = \
                    self._parse_decls([f'--{prefix}-{cli_name}-column'], True)
        else:
            cli_name = q2cli.util.to_cli_name(name)
            opt = f'--{prefix}-{cli_name}'

        click_type = QIIME2Type(ast, repr, is_output=prefix == 'o')
        attrs['metavar'] = metavar
        attrs['multiple'] = multiple is not None
        attrs['param_decls'] = [opt]
        attrs['required'] = default is NoDefault
        attrs['help'] = self._add_default(description, default)
        if default is not NoDefault:
            attrs['default'] = default

        # This is to evade clicks __DEBUG__ check
        if not is_bool_flag:
            attrs['type'] = click_type
        else:
            attrs['type'] = None

        # This nonsense:
        # https://github.com/pallets/click/blob
        # /08f71b08e2b7ee9b1ea27daf6d3040999fc68551
        # /src/click/core.py#L2576-L2584
        if is_bool_flag and multiple is not None:
            to_add_multiple = attrs.pop('multiple')

        super().__init__(**attrs)

        if is_bool_flag and multiple is not None:
            self.multiple = to_add_multiple

        # put things back the way they _should_ be after evading __DEBUG__
        self.is_bool_flag = is_bool_flag
        self.type = click_type

        # attrs we will use elsewhere
        self.q2_multiple = multiple
        self.q2_prefix = prefix
        self.q2_name = name
        self.q2_ast = ast
        self.q2_metadata = metadata

    @property
    def meta_help(self):
        if self.q2_metadata == 'file':
            return 'multiple arguments will be merged'

    def _add_default(self, desc, default):
        if desc is not None:
            desc += '  '
        else:
            desc = ''
        if default is not NoDefault:
            if default is None:
                desc += '[optional]'
            else:
                desc += '[default: %r]' % (default,)
        return desc

    def consume_value(self, ctx, opts):
        if self.q2_metadata == 'column':
            return self._consume_metadata(ctx, opts)
        else:
            return super().consume_value(ctx, opts)

    def _consume_metadata(self, ctx, opts):
        # double consume
        md_file, source = super().consume_value(ctx, opts)
        # consume uses self.name, so mutate but backup for after
        backup, self.name = self.name, self.q2_extra_dest
        md_col, _ = super().consume_value(ctx, opts)

        self.name = backup

        if (md_col is None) != (md_file is None):
            # missing one or the other
            if md_file is None:
                raise click.MissingParameter(ctx=ctx, param=self)
            else:
                raise click.MissingParameter(param_hint=self.q2_extra_opts,
                                             ctx=ctx, param=self)

        if md_col is None and md_file is None:
            return (None, source)
        else:
            return ((md_file, md_col), source)

    def get_help_record(self, ctx):
        record = super().get_help_record(ctx)
        if self.is_bool_flag:
            metavar = self.make_metavar()
            if metavar:
                record = (record[0] + ' ' + self.make_metavar(), record[1])
        elif self.q2_metadata == 'column':
            opts = (record[0], self.q2_extra_opts[0] + ' COLUMN ')
            record = (opts, record[1])
        return record

    # Override
    def add_to_parser(self, parser, ctx):
        shared = dict(dest=self.name, nargs=0, obj=self)
        if self.q2_metadata == 'column':
            parser.add_option(opts=self.opts, action='store', dest=self.name,
                              nargs=1, obj=self)
            parser.add_option(opts=self.q2_extra_opts, action='store',
                              dest=self.q2_extra_dest, nargs=1, obj=self)
        elif self.is_bool_flag:
            if self.multiple:
                action = 'append_maybe'
            else:
                action = 'store_maybe'
            parser.add_option(opts=self.opts, action=action, const=True,
                              **shared)
            parser.add_option(opts=self.secondary_opts, action=action,
                              const=False, **shared)
        elif self.multiple:
            action = 'append_greedy'
            parser.add_option(opts=self.opts, action='append_greedy', **shared)
        else:
            super().add_to_parser(parser, ctx)

    def get_default(self, ctx, call=True):
        if self.required and not ctx.resilient_parsing and not (
                self.q2_prefix == 'o' and ctx.params.get('output_dir', False)):
            raise click.MissingParameter(ctx=ctx, param=self)
        return super().get_default(ctx, call=call)

    def process_value(self, ctx, value):
        try:
            return super().process_value(ctx, value)
        except click.MissingParameter:
            if not (self.q2_prefix == 'o'
                    and ctx.params.get('output_dir', False)):
                raise

    def type_cast_value(self, ctx, value):
        import sys
        import q2cli.util
        import qiime2.sdk.util

        if self.multiple:
            if value == () or value is None:
                return None
            elif self.q2_prefix == 'i':
                value = super().type_cast_value(ctx, value)
                keys, value = self._split_and_validate_input_keys(value)

                if self.q2_multiple is set:
                    self._check_length(value, ctx)

                # This means we loaded a proper Collection directory. When we
                # load in a Collection directory for an action that takes a
                # Collection input, we get a tuple containing a dictionary of
                # the Collection we wanted. When we load in a Collection
                # directory for an action that takes a List, we get a list
                # containing a dictionary of the Collection we wanted. We just
                # extract that dictionary.
                if (isinstance(value, tuple) or isinstance(value, list)) \
                        and len(value) == 1 and isinstance(value[0], dict):
                    value = value[0]

                # We already have a dict, so we already have keys
                if isinstance(value, dict):
                    keys = value.keys()
                    value = list(value.values())
                elif self.q2_multiple is dict:
                    if keys is None:
                        keys = range(len(value))
                    value = value
                else:
                    value = self.q2_multiple(value)

                type_expr = qiime2.sdk.util.type_from_ast(self.q2_ast)
                args = ', '.join(map(repr, (x.type for x in value)))

                if value not in type_expr:
                    raise click.BadParameter(
                        'received <%s> as an argument, which is incompatible'
                        ' with parameter type: %r' % (args, type_expr),
                        ctx=ctx, param=self)

                if self.q2_multiple is dict:
                    value = {k: v for k, v in zip(keys, value)}
                return value
            elif self.q2_metadata == 'file':
                value = super().type_cast_value(ctx, value)
                if len(value) == 1:
                    return value[0]
                else:
                    try:
                        return value[0].merge(*value[1:])
                    except Exception as e:
                        header = ("There was an issue with merging "
                                  "QIIME 2 Metadata:")
                        tb = 'stderr' if '--verbose' in sys.argv else None
                        q2cli.util.exit_with_error(
                            e, header=header, traceback=tb)
            elif self.q2_prefix == 'p':
                try:
                    _values = []

                    if self.q2_multiple is set:
                        self._check_length(value, ctx)

                    keys = []
                    if self.q2_multiple is dict:
                        _values = {}

                        keyed = False
                        unkeyed = False
                        # All params in a Collection must be either keyed or
                        # unkeyed. We cannot have a mix because it makes things
                        # ambiguous
                        for idx, item in enumerate(value):
                            if ':' in item:
                                if unkeyed:
                                    raise KeyError(
                                        'The keyed value <%s> has been mixed'
                                        ' with unkeyed values. All values must'
                                        ' be keyed or unkeyed.' % item)
                                key, _value = item.split(':', 1)
                                _values[key] = _value
                                keyed = True
                            else:
                                if keyed:
                                    raise KeyError(
                                        'The unkeyed value <%s> has been'
                                        ' mixed with keyed values. All values'
                                        ' must be keyed or unkeyed.' % item)
                                _values[str(idx)] = item
                                unkeyed = True
                    else:
                        _values = value

                    value = \
                        qiime2.sdk.util.parse_primitive(self.q2_ast, _values)
                except ValueError:
                    args = ', '.join(map(repr, value))
                    expr = qiime2.sdk.util.type_from_ast(self.q2_ast)
                    raise click.BadParameter(
                        'received <%s> as an argument, which is incompatible'
                        ' with parameter type: %r' % (args, expr),
                        ctx=ctx, param=self)
                return value
        elif self.q2_prefix == 'i':
            value = super().type_cast_value(ctx, value)
            if value is not None:
                return value[1]
            return value

        # We have an output here
        return super().type_cast_value(ctx, value)

    def _split_and_validate_input_keys(self, value):
        """ This function ensures that if a user passed in a de-facto
            collection they did so properly.
        """
        keys = [t[0] for t in value]
        values = [t[1] for t in value]

        if any(key is not None and not key.isidentifier() for key in keys):
            raise ValueError('All keys must be valid Python identifiers.'
                             ' Python identifier rules may be found here'
                             ' https://www.askpython.com/python/'
                             'python-identifiers-rules-best-practices')

        # If we had no keys, we are fine
        if all(key is None for key in keys):
            return None, values

        has_nones = any(key is None for key in keys)
        has_keys = any(key is not None for key in keys)

        # We cannot have keys for something that isn't a dict
        if self.q2_multiple is not dict and has_keys:
            raise ValueError('Keyed values may only be supplied for '
                             'Collection inputs.')
        # We cannot have a mixture of keyed and unkeyed values
        elif self.q2_multiple is dict and has_keys and has_nones:
            raise ValueError('Keyed values cannot be mixed with unkeyed '
                             'values.')

        return keys, values

    def _check_length(self, value, ctx):
        import collections

        # TODO: Ok seriously though figure out why value is in a tuple if it is
        # a Collection
        if isinstance(value, tuple) and len(value) == 1 and \
                isinstance(value[0], dict):
            value = list(value[0].values())

        counter = collections.Counter(value)

        dups = ', '.join(map(repr, (v for v, n in counter.items() if n > 1)))
        args = ', '.join(map(repr, value))
        if dups:
            raise click.BadParameter(
                'received <%s> as an argument, which contains duplicates'
                ' of the following: <%s>' % (args, dups), ctx=ctx, param=self)
