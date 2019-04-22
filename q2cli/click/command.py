import click

from .parser import Q2Parser


class BaseCommandMixin:
    def make_parser(self, ctx):
        """Creates the underlying option parser for this command."""
        parser = Q2Parser(ctx)
        for param in self.get_params(ctx):
            param.add_to_parser(parser, ctx)
        return parser

    def list_commands(self, ctx):
        if not hasattr(super(), 'list_commands'):
            return []
        return super().list_commands(ctx)

    def format_usage(self, ctx, formatter):
        pieces = self.collect_usage_pieces(ctx)
        formatter.write_usage(
            click.style(ctx.command_path, fg='cyan', bold=True),
            ' '.join(pieces))

    def format_options(self, ctx, formatter):
        """Writes all the options into the formatter if they exist."""
        opts = []
        for param in self.get_params(ctx):
            rv = param.get_help_record(ctx)
            if rv is not None:
                opts.append(rv)

        if opts:
            with formatter.section('Options'):
                self.write_dl2(formatter, opts, dense=False)

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
                rows.append((subcommand, help))

            if rows:
                with formatter.section('Commands'):
                    self.write_dl2(formatter, rows, dense=True)

    def write_dl2(self, formatter, rows, dense=True, COL_MAX=22, COL_MIN=10, COL_SPACING=2):
        import itertools

        rows = list(rows)

        # Only measure up to the first METAVAR, toss anything else, as it will
        # be line-wrapped
        measured = (first for first, _ in rows)
        first_width = max(click.formatting.term_len(r) for r in measured)

        first_width = max(min(first_width, COL_MAX), COL_MIN)
        second_width = max(
            formatter.width - formatter.current_indent - first_width - COL_SPACING,
            COL_MIN)

        last = len(rows) - 1
        for idx, (first, second) in enumerate(rows):
            first_head, first_tail = self._fmt_option(first)
           # first_tail = click.formatting.wrap_text(first_tail,
           #                                         first_width, subsequent_indent='  ', initial_indent='  ').splitlines()
            first = [first_head + " " + first_tail]

            default = max(second.find('[default:'), second.find('[required'), second.find('[optional'))
            if default >= 0:
                default_help = click.style(second[default:], fg='magenta')
                second = second[:default]
            else:
                default_help = ''

            second = click.formatting.wrap_text(second,
                                                second_width).splitlines()
            if len(second) == 0 or click.formatting.term_len(default_help) > (second_width - 2 - click.formatting.term_len(second[-1])):
                second.append(default_help)
            else:
                second[-1] += '  ' + default_help

            if len(first) > len(second):
                second.extend([''] * (len(first) - len(second)))

            if idx != last and False:
                second[-1] = click.style(second[-1] + ' ' * (second_width - len(second[-1])), underline=True)

            if click.formatting.term_len(first[0]) > first_width + 1:
                formatter.write((' ' * formatter.current_indent) + first.pop(0) + '\n')

            lines = []
            for f, s in itertools.zip_longest(first, second, fillvalue=''):
                f += ' ' * (first_width - click.formatting.term_len(f) + COL_SPACING)
                formatter.write((' ' * (formatter.current_indent)) + f + s + '\n')

    def _fmt_option(self, opt_text):
        components = opt_text.split(' ')
        if ' / -' in opt_text:
            head, tail = components[:3], components[3:]
            head = ' / '.join([click.style(head[0], fg='cyan', bold=True), click.style(head[2], fg='cyan', bold=True)])
        else:
            head, tail = components[0], components[1:]
            head = click.style(head, fg='cyan', bold=True)

        return head, ' '.join(tail)


class ToolCommand(BaseCommandMixin, click.Command):
    pass


class ToolGroupCommand(BaseCommandMixin, click.Group):
    pass
