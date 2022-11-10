# ----------------------------------------------------------------------------
# Copyright (c) 2016-2022, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------


class ControlFlowException(Exception):
    pass


def get_app_dir():
    import os
    conda_prefix = os.environ.get('CONDA_PREFIX')
    if conda_prefix is not None and os.access(conda_prefix, os.W_OK | os.X_OK):
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


def to_snake_case(name):
    return name.replace('-', '_')


def exit_with_error(e, header='An error has been encountered:',
                    traceback='stderr', status=1):
    import sys
    import traceback as tb
    import textwrap
    import click
    from q2cli.core.config import CONFIG

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

    click.echo(CONFIG.cfg_style('error', '\n\n'.join(segments)), err=True)

    if not footer:
        click.echo(err=True)  # extra newline to look normal

    click.get_current_context().exit(status)


def output_in_cache(fp):
    """Determines if an output path follows the format
    /path_to_extant_cache:key
    """
    from qiime2.core.cache import Cache

    # Tells us right away this isn't in a cache
    if ':' not in fp:
        return False

    cache_path, key = _get_cache_path_and_key(fp)

    try:
        if Cache.is_cache(cache_path):
            if not key.isidentifier():
                raise ValueError(
                    'Key must be a valid Python identifier. Python identifier '
                    'rules may be found here https://www.askpython.com/python/'
                    'python-identifiers-rules-best-practices')
            else:
                return True
    except FileNotFoundError as e:
        # If cache_path doesn't exist, don't treat this as a cache output
        if 'No such file or directory' in str(e):
            pass
        else:
            raise e

    # We don't have a cache at all
    return False


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
    from q2cli.core.config import CONFIG

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
            click.echo(
                CONFIG.cfg_style('problem', 'No citations found.'), err=True)
            ctx.exit(1)

    return click.Option(['--citations'], is_flag=True, expose_value=False,
                        is_eager=True, callback=callback,
                        help='Show citations and exit.')


def example_data_option(get_plugin, action_name=None):
    import click
    from q2cli.click.type import OutDirType

    def callback(ctx, param, value):
        if not value or ctx.resilient_parsing:
            return
        else:
            import q2cli.core.usage as usage

        plugin = get_plugin()
        if action_name is not None:
            action = plugin.actions[action_name]
            generator = usage.write_example_data(action, value)
        else:
            generator = usage.write_plugin_example_data(plugin, value)

        ran = False
        for hint, path in generator:
            click.secho('Saved %s to: %s' % (hint, path), fg='green')
            ran = True

        if ran:
            ctx.exit()
        else:
            click.secho('No example data found.', fg='yellow', err=True)
            ctx.exit(1)

    return click.Option(['--example-data'], type=OutDirType(), is_eager=True,
                        expose_value=False, callback=callback,
                        help='Write example data and exit.')


def get_plugin_manager():
    import qiime2.sdk

    try:
        return qiime2.sdk.PluginManager.reuse_existing()
    except qiime2.sdk.UninitializedPluginManagerError:
        import os

        if 'MYSTERY_STEW' in os.environ:
            from q2_mystery_stew.plugin_setup import create_plugin

            the_stew = create_plugin()
            pm = qiime2.sdk.PluginManager(add_plugins=False)
            pm.add_plugin(the_stew)
            return pm

        return qiime2.sdk.PluginManager()


def load_metadata(fp):
    """ Turns a filepath into metadata if the path is either to metadata or an
    artifact that can be viewed as metadata
    """
    import sys
    import qiime2

    try:
        artifact = get_input(fp)
    # With a ControlFlowException, we don't know why we couldn't load it as an
    # artifact, so it could still be a metadata file. With the other exception
    # types, we do know why we couldn't load it, and we know it just isn't a
    # valid file at all.
    except ControlFlowException:
        try:
            return qiime2.Metadata.load(fp)
        except Exception as e:
            # Handle the case where we try to load a raw .qza as Metadata
            # because we were missing the plugin(s) necessary to load it as an
            # Artifact
            if "'utf-8' codec can't decode byte" in str(e) and \
                    qiime2.sdk.result.Result.peek(fp):
                e = ValueError("It looks like you have an Artifact but are "
                               "missing the plugin(s) necessary to load it.")

            header = ("There was an issue with loading the file %s as "
                      "metadata:" % fp)
            tb = 'stderr' if '--verbose' in sys.argv else None
            exit_with_error(e, header=header, traceback=tb)

    if isinstance(artifact, qiime2.Visualization):
        raise Exception(
            f'Visualizations cannot be viewed as QIIME 2 metadata:\n{fp}')
    elif artifact.has_metadata():
        try:
            metadata = artifact.view(qiime2.Metadata)
        except Exception as e:
            header = ("There was an issue with viewing the artifact "
                      "%s as QIIME 2 Metadata:" % fp)
            tb = 'stderr' if '--verbose' in sys.argv else None
            exit_with_error(e, header=header, traceback=tb)
    else:
        raise Exception("Artifacts with type %r cannot be viewed as"
                        " QIIME 2 metadata:\n%r" % (artifact.type, fp))

    return metadata


def get_input(fp):
    """ Gets a Result from a filepath if possible
    """
    import tempfile
    import qiime2
    import qiime2.sdk

    get_plugin_manager()
    try:
        artifact = None

        if ':' in fp:
            artifact = try_as_cache_input(fp)

        # If we get here we either had a path without a ':' or we got
        # None from try_as_cache_input meaning the part of value
        # before the ':' was not an existing cache
        if artifact is None:
            artifact = qiime2.sdk.Result.load(fp)
    except OSError as e:
        if e.errno == 28:
            temp = tempfile.tempdir
            raise ValueError(f'There was not enough space left on {temp!r} '
                             f'to extract the artifact {fp!r}. (Try '
                             'setting $TMPDIR to a directory with more '
                             f'space, or increasing the size of {temp!r})')
        else:
            raise ControlFlowException(
                '%r is not a QIIME 2 Artifact (.qza)' % fp)
    except KeyError as e:
        if 'does not contain the key' in str(e):
            raise e
        else:
            raise ControlFlowException(
                '%r is not a QIIME 2 Artifact (.qza):\n%s' % (fp, str(e)))
    except ValueError as e:
        if 'does not exist' in str(e):
            # If value was also not an existing filepath
            # containing a ':' we assume they wanted a cache
            # but did not provide a valid one
            if ':' in fp:
                raise ValueError(f"The path {fp.split(':')[0]} is not a valid"
                                 " cache")
            else:
                raise ValueError(f'{fp!r} is not a valid filepath:\n{str(e)}')
        else:
            raise ControlFlowException(
                '%r is not a QIIME 2 Artifact (.qza):\n%s' % (fp, str(e)))
    # If we get here, all we really know is we failed to get a Result
    except Exception as e:
        raise ControlFlowException(
            'There was a problem loading %s as a QIIME 2 Result:\n%s' %
            (fp, str(e)))

    return artifact


def try_as_cache_input(fp):
    """ Determine if an input is in a cache and load it from the cache if it is
    """
    import os
    from qiime2.core.cache import Cache

    cache_path, key = _get_cache_path_and_key(fp)

    # We don't want to invent a new cache on disk here because if their input
    # exists their cache must also already exist
    if not os.path.exists(cache_path) or not Cache.is_cache(cache_path):
        return None

    cache = Cache(cache_path)
    return cache.load(key)


def _get_cache_path_and_key(fp):
    return fp.rsplit(':', 1)
