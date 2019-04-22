# ----------------------------------------------------------------------------
# Copyright (c) 2016-2019, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------


def get_app_dir():
    import os
    conda_prefix = os.environ.get('CONDA_PREFIX')
    if conda_prefix is not None:
        return os.path.join(conda_prefix, 'var', 'q2cli')
    else:
        import click
        return click.get_app_dir('q2cli', roaming=False)


# NOTE: `get_cache_dir` and `get_completion_path` live here instead of
# `q2cli.cache` because `q2cli.cache` can be  slow to import.
# `get_completion_path` (which relies on `get_cache_dir`) is imported and
# executed by the Bash completion function each time the user hits <tab>, so it
# must be quick to import.
def get_cache_dir():
    import os.path
    return os.path.join(get_app_dir(), 'cache')


def get_completion_path():
    import os.path
    return os.path.join(get_cache_dir(), 'completion.sh')


def to_cli_name(name):
    return name.replace('_', '-')


def exit_with_error(e, header='An error has been encountered:',
                    traceback='stderr', status=1):
    import sys
    import traceback as tb
    import textwrap
    import click

    footer = []  # footer only exists if traceback is set
    tb_file = None
    if traceback == 'stderr':
        tb_file = sys.stderr
        footer = ['See above for debug info.']
    elif traceback is not None:
        tb_file = traceback
        footer = ['Debug info has been saved to %s' % tb_file.name]

    error = textwrap.indent(str(e), '  ')
    segments = [header, error] + footer

    if traceback is not None:
        tb.print_exception(type(e), e, e.__traceback__, file=tb_file)

        tb_file.write('\n')

    click.secho('\n\n'.join(segments), fg='red', bold=True, err=True)

    if not footer:
        click.echo(err=True)  # extra newline to look normal

    click.get_current_context().exit(status)


def get_close_matches(name, possibilities):
    import difflib

    name = name.lower()
    # bash completion makes an incomplete arg most likely
    matches = [m for m in possibilities if m.startswith(name)]
    if not matches:
        # otherwise, it may be misspelled
        matches = difflib.get_close_matches(name, possibilities, cutoff=0.8)

    matches.sort()

    if len(matches) > 5:
        # this is probably a good time to look at --help
        matches = matches[:4] + ['...']

    return matches


class pretty_failure:
    def __init__(self, header='An error has been encountered:',
                 traceback='stderr', status=1):
        self.header = header
        self.traceback = traceback
        self.status = status

    def __call__(self, function):
        def wrapped(*args, **kwargs):
            with self:
                return function(*args, **kwargs, failure=self)
        # not using functools.wraps to keep import overhead low
        # click only seems to need the __name__
        wrapped.__name__ = function.__name__
        return wrapped

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            exit_with_error(exc_val, self.header, self.traceback, self.status)

        return True


def convert_primitive(ast):
    import click

    mapping = {
        'Int': int,
        'Str': str,
        'Float': float,
        'Color': str,
        'Bool': bool
    }
    # TODO: it would be a good idea to refactor this someday, but until then
    # just handle the few predicates we know about.
    predicate = ast['predicate']
    if predicate:
        if predicate['name'] == 'Choices' and ast['name'] == 'Str':
            return click.Choice(predicate['choices'])
        elif predicate['name'] == 'Range' and ast['name'] == 'Int':
            start = predicate['range'][0]
            end = predicate['range'][1]
            # click.IntRange is always inclusive
            if start is not None and not predicate['inclusive'][0]:
                start += 1
            if end is not None and not predicate['inclusive'][1]:
                end -= 1
            return click.IntRange(start, end)
        elif predicate['name'] == 'Range' and ast['name'] == 'Float':
            # click.FloatRange will be in click 7.0, so for now the
            # range handling will just fallback to qiime2.
            return mapping['Float']
        else:
            raise NotImplementedError()
    else:
        return mapping[ast['name']]


def citations_option(get_citation_records):
    import click

    def callback(ctx, param, value):
        if not value or ctx.resilient_parsing:
            return

        records = get_citation_records()
        if records:
            import io
            import qiime2.sdk

            citations = qiime2.sdk.Citations(
                [('key%d' % i, r) for i, r in enumerate(records)])
            with io.StringIO() as fh:
                fh.write('% use `qiime tools citations` on a QIIME 2 result'
                         ' for complete list\n\n')
                citations.save(fh)
                click.echo(fh.getvalue(), nl=False)
            ctx.exit()
        else:
            click.secho('No citations found.', fg='yellow', err=True)
            ctx.exit(1)

    return click.Option(('--citations',), is_flag=True, expose_value=False,
                        is_eager=True, callback=callback,
                        help='Show citations and exit.')



def find_inputs(type, dir=None):
    import qiime2.sdk as sdk
    import os

    type = sdk.parse_type(type)
    if dir is None:
        for path in os.scandir(dir):
            name = path.name
            if path.is_dir() or not name.endswith('.qza'):
                continue
            t = sdk.parse_type(sdk.Artifact.peek(name).type)
            if t <= type:
                yield name
    else:
        for path in os.scandir(dir):
            name = os.path.join(dir, path.name)
            if path.is_dir() or not name.endswith('.qza'):
                continue
            t = sdk.parse_type(sdk.Artifact.peek(name).type)
            if t <= type:
                yield name

