# ----------------------------------------------------------------------------
# Copyright (c) 2016-2019, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import click
import click.core

from .parser import Q2Parser


class BaseCommandMixin:
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

    def make_parser(self, ctx):
        """Creates the underlying option parser for this command."""
        parser = Q2Parser(ctx)
        for param in self.get_params(ctx):
            param.add_to_parser(parser, ctx)
        return parser

    def parse_args(self, ctx, args):
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
            click.secho(
                'There were some problem(s) with this command'.center(78, ' '),
                fg='yellow', err=True)
            for idx, e in enumerate(errors, 1):
                msg = click.formatting.wrap_text(
                    e.format_message(),
                    initial_indent=' (%d/%d%s) ' % (idx, len(errors),
                                                    '?' if skip_rest else ''),
                    subsequent_indent='  ')
                click.secho(msg, err=True, fg='red', bold=True)
            ctx.exit(1)

        ctx.args = args
        return args

    def list_commands(self, ctx):
        if not hasattr(super(), 'list_commands'):
            return []
        return super().list_commands(ctx)

    def format_usage(self, ctx, formatter):
        pieces = self.collect_usage_pieces(ctx)
        formatter.write_usage(_style_command(ctx.command_path),
                              ' '.join(pieces))

    def get_opt_groups(self, ctx):
        return {'Options': list(self.get_params(ctx))}

    def format_help_text(self, ctx, formatter):
        super().format_help_text(ctx, formatter)
        formatter.write_paragraph()

    def format_options(self, ctx, formatter, COL_MAX=23, COL_MIN=10):
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

        # write subcommands
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
                rows.append((_style_command(subcommand), help))

            if rows:
                with formatter.section('Commands'):
                    formatter.write_dl(rows)

    def write_option(self, ctx, formatter, opt, record, border, COL_SPACING=2):
        import itertools
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
                    token = _style_option(token, required=opt.required)
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
                    line = " " + _style_type(line)
                    first_iter = False
                else:
                    dangling_edge = len(type_indent) + len(line)
                    line = type_indent + _style_type(line)
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
            line = ''.join([type_indent, _style_type(type_repr), padding])
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

            formatter.write((' ' * pad) + _style_reqs(requirements) + '\n')

    def _color_important(self, tokens, ctx):
        import re

        for t in tokens:
            if '_' in t:
                names = self.get_option_names(ctx)
                if re.sub(r'[^\w]', '', t) in names:
                    m = re.search(r'(\w+)', t)
                    word = t[m.start():m.end()]
                    word = _style_emphasis(word.replace('_', '-'))
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


def _style_option(text, required=False):
    return click.style(text, fg='blue', bold=True, underline=required)


def _style_type(text):
    return click.style(text, fg='green')


def _style_reqs(text):
    return click.style(text, fg='magenta')


def _style_command(text):
    return _style_option(text)


def _style_emphasis(text):
    return click.style(text, underline=True)
