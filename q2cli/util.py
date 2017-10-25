# ----------------------------------------------------------------------------
# Copyright (c) 2016-2017, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------


def get_app_dir():
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


def exit_with_error(e, header='An error has been encountered:', file=None,
                    suppress_footer=False):
    import sys
    import traceback
    import textwrap
    import click

    if file is None:
        file = sys.stderr
        footer = 'See above for debug info.'
    else:
        footer = 'Debug info has been saved to %s' % file.name

    error = textwrap.indent(
        '\n'.join(textwrap.wrap(str(e))), '  ')

    segments = [header, error]
    if not suppress_footer:
        segments.append(footer)

    traceback.print_exception(type(e), e, e.__traceback__, file=file)
    file.write('\n')

    click.secho('\n\n'.join(segments), fg='red', bold=True, err=True)

    click.get_current_context().exit(1)


def convert_primitive(ast):
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
    predicate = ast['predicate']
    if predicate:
        if predicate['name'] == 'Choices' and ast['name'] == 'Str':
            return click.Choice(predicate['choices'])
        elif predicate['name'] == 'Range' and ast['name'] == 'Int':
            start = predicate['start']
            end = predicate['end']
            # click.IntRange is always inclusive
            if start is not None and not predicate['inclusive-start']:
                start += 1
            if end is not None and not predicate['inclusive-end']:
                end -= 1
            return click.IntRange(start, end)
        elif predicate['name'] == 'Range' and ast['name'] == 'Float':
            # click.FloatRange will be in click 7.0, so for now the
            # range handling will just fallback to qiime2.
            return mapping['Float']
        else:
            raise NotImplementedError()
