# ----------------------------------------------------------------------------
# Copyright (c) 2016-2019, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
# Some of the source code in this file is derived from original work:
#
# Copyright (c) 2014 by the Pallets team.
#
# To see the license for the original work, see licenses/click.LICENSE.rst
# Specific reproduction and derivation of original work is marked below.
# ----------------------------------------------------------------------------

import click
import click.core


class BaseCommandMixin:
    # Modified from original:
    # < https://github.com/pallets/click/blob/
    #   c6042bf2607c5be22b1efef2e42a94ffd281434c/click/core.py#L867 >
    # Copyright (c) 2014 by the Pallets team.
    def make_parser(self, ctx):
        """Creates the underlying option parser for this command."""
        from .parser import Q2Parser

        parser = Q2Parser(ctx)
        for param in self.get_params(ctx):
            param.add_to_parser(parser, ctx)
        return parser

    # Modified from original:
    # < https://github.com/pallets/click/blob/
    #   c6042bf2607c5be22b1efef2e42a94ffd281434c/click/core.py#L934 >
    # Copyright (c) 2014 by the Pallets team.
    def parse_args(self, ctx, args):
        from q2cli.core.config import CONFIG
        if isinstance(self, click.MultiCommand):
            return super().parse_args(ctx, args)

        errors = []
        parser = self.make_parser(ctx)
        skip_rest = False
        for _ in range(10):  # surely this is enough attempts
            try:
                opts, args, param_order = parser.parse_args(args=args)
                break
            except click.ClickException as e:
                errors.append(e)
                skip_rest = True

        if not skip_rest:
            for param in click.core.iter_params_for_processing(
                    param_order, self.get_params(ctx)):
                try:
                    value, args = param.handle_parse_result(ctx, opts, args)
                except click.ClickException as e:
                    errors.append(e)

            if args and not ctx.allow_extra_args and not ctx.resilient_parsing:
                errors.append(click.UsageError(
                    'Got unexpected extra argument%s (%s)'
                    % (len(args) != 1 and 's' or '',
                       ' '.join(map(click.core.make_str, args)))))
        if errors:
            click.echo(ctx.get_help()+"\n", err=True)
            if len(errors) > 1:
                problems = 'There were some problems with the command:'
            else:
                problems = 'There was a problem with the command:'
            click.echo(CONFIG.cfg_style('problem',
                       problems.center(78, ' ')), err=True)
            for idx, e in enumerate(errors, 1):
                msg = click.formatting.wrap_text(
                    e.format_message(),
                    initial_indent=' (%d/%d%s) ' % (idx, len(errors),
                                                    '?' if skip_rest else ''),
                    subsequent_indent='  ')
                click.echo(CONFIG.cfg_style('error', msg), err=True)
            ctx.exit(1)

        ctx.args = args
        return args

    def get_option_names(self, ctx):
        if not hasattr(self, '__option_names'):
            names = set()
            for param in self.get_params(ctx):
                if hasattr(param, 'q2_name'):
                    names.add(param.q2_name)
                else:
                    names.add(param.name)
            self.__option_names = names

        return self.__option_names

    def list_commands(self, ctx):
        if not hasattr(super(), 'list_commands'):
            return []
        return super().list_commands(ctx)

    def get_opt_groups(self, ctx):
        return {'Options': list(self.get_params(ctx))}

    def format_help_text(self, ctx, formatter):
        super().format_help_text(ctx, formatter)
        formatter.write_paragraph()

    # Modified from original:
    # < https://github.com/pallets/click/blob
    #   /c6042bf2607c5be22b1efef2e42a94ffd281434c/click/core.py#L830 >
    # Copyright (c) 2014 by the Pallets team.
    def format_usage(self, ctx, formatter):
        from q2cli.core.config import CONFIG
        """Writes the usage line into the formatter."""
        pieces = self.collect_usage_pieces(ctx)
        formatter.write_usage(CONFIG.cfg_style('command', ctx.command_path),
                              ' '.join(pieces))

    def format_options(self, ctx, formatter, COL_MAX=23, COL_MIN=10):
        from q2cli.core.config import CONFIG
        # write options
        opt_groups = {}
        records = []
        for group, options in self.get_opt_groups(ctx).items():
            opt_records = []
            for o in options:
                record = o.get_help_record(ctx)
                if record is None:
                    continue
                opt_records.append((o, record))
                records.append(record)
            opt_groups[group] = opt_records
        first_columns = (r[0] for r in records)
        border = min(COL_MAX, max(COL_MIN, *(len(col) for col in first_columns
                                             if len(col) < COL_MAX)))

        for opt_group, opt_records in opt_groups.items():
            if not opt_records:
                continue
            formatter.write_heading(click.style(opt_group, bold=True))
            formatter.indent()
            padded_border = border + formatter.current_indent
            for opt, record in opt_records:
                self.write_option(ctx, formatter, opt, record, padded_border)
            formatter.dedent()

        # Modified from original:
        # https://github.com/pallets/click/blob
        # /c6042bf2607c5be22b1efef2e42a94ffd281434c/click/core.py#L1056
        # Copyright (c) 2014 by the Pallets team.
        commands = []
        for subcommand in self.list_commands(ctx):
            cmd = self.get_command(ctx, subcommand)
            # What is this, the tool lied about a command.  Ignore it
            if cmd is None:
                continue
            if cmd.hidden:
                continue

            commands.append((subcommand, cmd))

        # allow for 3 times the default spacing
        if len(commands):
            limit = formatter.width - 6 - max(len(cmd[0]) for cmd in commands)

            rows = []
            for subcommand, cmd in commands:
                help = cmd.get_short_help_str(limit)
                rows.append((CONFIG.cfg_style('command', subcommand), help))

            if rows:
                with formatter.section(click.style('Commands', bold=True)):
                    formatter.write_dl(rows)

    def write_option(self, ctx, formatter, opt, record, border, COL_SPACING=2):
        import itertools
        from q2cli.core.config import CONFIG
        full_width = formatter.width - formatter.current_indent
        indent_text = ' ' * formatter.current_indent
        opt_text, help_text = record
        opt_text_secondary = None
        if type(opt_text) is tuple:
            opt_text, opt_text_secondary = opt_text
        help_text, requirements = self._clean_help(help_text)
        type_placement = None
        type_repr = None
        type_indent = 2 * indent_text

        if hasattr(opt.type, 'get_type_repr'):
            type_repr = opt.type.get_type_repr(opt)
            if type_repr is not None:
                if len(type_repr) <= border - len(type_indent):
                    type_placement = 'under'
                else:
                    type_placement = 'beside'

        if len(opt_text) > border:
            lines = simple_wrap(opt_text, full_width)
        else:
            lines = [opt_text.split(' ')]
        if opt_text_secondary is not None:
            lines.append(opt_text_secondary.split(' '))

        to_write = []
        for tokens in lines:
            dangling_edge = formatter.current_indent
            styled = []
            for token in tokens:
                dangling_edge += len(token) + 1
                if token.startswith('--'):
                    token = CONFIG.cfg_style('option', token,
                                             required=opt.required)
                styled.append(token)
            line = indent_text + ' '.join(styled)
            to_write.append(line)
        formatter.write('\n'.join(to_write))
        dangling_edge -= 1

        if type_placement == 'beside':
            lines = simple_wrap(type_repr, formatter.width - len(type_indent),
                                start_col=dangling_edge - 1)
            to_write = []
            first_iter = True
            for tokens in lines:
                line = ' '.join(tokens)
                if first_iter:
                    dangling_edge += 1 + len(line)
                    line = " " + CONFIG.cfg_style('type', line)
                    first_iter = False
                else:
                    dangling_edge = len(type_indent) + len(line)
                    line = type_indent + CONFIG.cfg_style('type', line)
                to_write.append(line)
            formatter.write('\n'.join(to_write))

        if dangling_edge + 1 > border + COL_SPACING:
            formatter.write('\n')
            left_col = []
        else:
            padding = ' ' * (border + COL_SPACING - dangling_edge)
            formatter.write(padding)
            dangling_edge += len(padding)
            left_col = ['']  # jagged start

        if type_placement == 'under':
            padding = ' ' * (border + COL_SPACING
                             - len(type_repr) - len(type_indent))
            line = ''.join(
                [type_indent, CONFIG.cfg_style('type', type_repr), padding])
            left_col.append(line)

        if hasattr(opt, 'meta_help') and opt.meta_help is not None:
            meta_help = simple_wrap(opt.meta_help,
                                    border - len(type_indent) - 1)
            for idx, line in enumerate([' '.join(t) for t in meta_help]):
                if idx == 0:
                    line = type_indent + '(' + line
                else:
                    line = type_indent + ' ' + line
                if idx == len(meta_help) - 1:
                    line += ')'
                line += ' ' * (border - len(line) + COL_SPACING)
                left_col.append(line)

        right_col = simple_wrap(help_text,
                                formatter.width - border - COL_SPACING)
        right_col = [' '.join(self._color_important(tokens, ctx))
                     for tokens in right_col]

        to_write = []
        for left, right in itertools.zip_longest(
                left_col, right_col, fillvalue=' ' * (border + COL_SPACING)):
            to_write.append(left)
            if right.strip():
                to_write[-1] += right

        formatter.write('\n'.join(to_write))

        if requirements is None:
            formatter.write('\n')
        else:
            if to_write:
                if len(to_write) > 1 or ((not left_col) or left_col[0] != ''):
                    dangling_edge = 0
                dangling_edge += click.formatting.term_len(to_write[-1])
            else:
                pass  # dangling_edge is still correct

            if dangling_edge + 1 + len(requirements) > formatter.width:
                formatter.write('\n')
                pad = formatter.width - len(requirements)
            else:
                pad = formatter.width - len(requirements) - dangling_edge

            formatter.write(
                (' ' * pad) + CONFIG.cfg_style(
                    'default_arg', requirements) + '\n')

    def _color_important(self, tokens, ctx):
        import re
        from q2cli.core.config import CONFIG

        for t in tokens:
            if '_' in t:
                names = self.get_option_names(ctx)
                if re.sub(r'[^\w]', '', t) in names:
                    m = re.search(r'(\w+)', t)
                    word = t[m.start():m.end()]
                    word = CONFIG.cfg_style('emphasis', word.replace('_', '-'))
                    token = t[:m.start()] + word + t[m.end():]
                    yield token
                    continue
            yield t

    def _clean_help(self, text):
        reqs = ['[required]', '[optional]', '[default: ']
        requirement = None
        for req in reqs:
            if req in text:
                requirement = req
                break
        else:
            return text, None

        req_idx = text.index(requirement)

        return text[:req_idx].strip(), text[req_idx:].strip()


class ToolCommand(BaseCommandMixin, click.Command):
    pass


class ToolGroupCommand(BaseCommandMixin, click.Group):
    pass


def simple_wrap(text, target, start_col=0):
    result = [[]]
    current_line = result[0]
    current_width = start_col
    tokens = []
    for token in text.split(' '):
        if len(token) <= target:
            tokens.append(token)
        else:
            for i in range(0, len(token), target):
                tokens.append(token[i:i+target])

    for token in tokens:
        token_len = len(token)
        if current_width + 1 + token_len > target:
            current_line = [token]
            result.append(current_line)
            current_width = token_len
        else:
            result[-1].append(token)
            current_width += 1 + token_len

    return result
