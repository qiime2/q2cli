# ----------------------------------------------------------------------------
# Copyright (c) 2016-2023, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------


class OutOfDisk(Exception):
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


def hidden_to_cli_name(name):
    # Safety first
    if not name.startswith('_'):
        raise ValueError(f"The name '{name}' does not start with '_' meaning"
                         " it is not a hidden action and this method should"
                         " not have been called on it.")

    name = to_cli_name(name)

    # Retain the leading _
    return name.replace('-', '_', 1)


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

    try:
        click.get_current_context().exit(status)
    except RuntimeError:
        sys.exit(status)


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
                    f"Key '{key}' is not a valid Python identifier. Keys must "
                    "be valid Python identifiers. Python identifier rules may "
                    "be found here https://www.askpython.com/python/"
                    "python-identifiers-rules-best-practices")
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
        # if exit_with_error is called twice, then click.exit(1) or sys.exit(1)
        # will happen, no need to exit_with_error again in that case.
        if exc_val is not None and str(exc_val) != '1':
            exit_with_error(exc_val, self.header, self.traceback, self.status)

        return False


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
    import qiime2
    import sys

    metadata, error = _load_metadata_artifact(fp)
    if metadata is None:
        try:
            metadata = qiime2.Metadata.load(fp)
        except Exception as e:
            if error and ':' in fp:
                e = error
            header = ("There was an issue with loading the file %s as "
                      "metadata:" % fp)
            tb = 'stderr' if '--verbose' in sys.argv else None
            exit_with_error(e, header=header, traceback=tb)

    return metadata


def _load_metadata_artifact(fp):
    import qiime2
    import sys

    artifact, error = _load_input(fp)
    artifact = artifact[1]
    if isinstance(error, OutOfDisk):
        raise error

    default_tb = 'stderr'
    # if that worked, we have an artifact or we've
    # already raised a critical error
    # otherwise, any normal errors can be ignored as its
    # most likely actually metadata not a qza
    if artifact:
        try:
            default_tb = None
            if isinstance(artifact, qiime2.Visualization):
                raise Exception(
                    'Visualizations cannot be viewed as QIIME 2 metadata.')
            if not artifact.has_metadata():
                raise Exception(
                    f"Artifacts with type {artifact.type!r} cannot be viewed"
                    " as QIIME 2 metadata.")

            default_tb = 'stderr'
            return artifact.view(qiime2.Metadata), None

        except Exception as e:
            header = ("There was an issue with viewing the artifact "
                      f"{fp!r} as QIIME 2 Metadata:")
            tb = 'stderr' if '--verbose' in sys.argv else default_tb
            exit_with_error(e, header=header, traceback=tb)

    else:
        return None, error


def _load_input(fp, view=False):
    # Just initialize the plugin manager. This is slow and not necessary if we
    # called this from qiime tools view.
    import os

    key = None

    if not view:
        _ = get_plugin_manager()

    # We are loading a collection from outside of a cache. This cannot be keyed
    if os.path.isdir(fp):
        if len(os.listdir(fp)) == 0:
            raise ValueError(f"Provided directory '{fp}' is empty.")

        artifact, error = _load_collection(fp)
    # We may be loading something from a cache with or without and additional
    # key, or we may be loading a piece of data from outside of a cache with a
    # key. We could also be loading a normal unkeyed artifact with a : in its
    # path
    elif ':' in fp:
        # First we assume this is just a weird filepath
        artifact, _ = _load_input_file(fp)
        # Then we check if it is a key:path
        if artifact is None:
            key, new_fp = _get_path_and_collection_key(fp)
            new_fp = os.path.expanduser(new_fp)
            artifact, _ = _load_input_file(new_fp)

        # If we still have nothing
        if artifact is None:
            key = None
            # We assume this is a cache:key. We keep this error because we
            # assume if they had a : in their path they were trying to load
            # something from a cache
            artifact, error = _load_input_cache(fp)
            if error:
                # Then we check if it is a key:cache:key
                key, new_fp = _get_path_and_collection_key(fp)
                artifact, _ = _load_input_cache(new_fp)

        # If we ended up with an artifact, we disregard our error
        if artifact is not None:
            error = None
    # We are just loading a normal artifact on disk without silly colons in the
    # filepath
    else:
        artifact, error = _load_input_file(fp)

    if isinstance(error, OSError) and error.errno == 28:
        # abort as there's nothing anyone can do about this
        from qiime2.core.cache import get_cache

        path = str(get_cache().path)
        return None, OutOfDisk(f'There was not enough space left on {path!r} '
                               f'to use the artifact {fp!r}. (Try '
                               f'setting $TMPDIR to a directory with more '
                               f'space, or increasing the size of {path!r})')

    return (key, artifact), error


# NOTE: These load collection functions are now virtually identical to class
# methods on qiime2.sdk.Result
def _load_collection(fp):
    import os
    import warnings

    order_fp = os.path.join(fp, '.order')

    if os.path.isfile(order_fp):
        artifacts, error = _load_ordered_collection(fp, order_fp)
    else:
        warnings.warn(f'The directory {fp} does not contain a .order file. '
                      'The files will be read into the collection in the '
                      'order the filesystem provides them in.')
        artifacts, error = _load_unordered_collection(fp)

    return artifacts, error


def _load_ordered_collection(fp, order_fp):
    import os

    artifacts = {}

    with open(order_fp) as order_fh:
        for key in order_fh.read().splitlines():
            artifact_path = os.path.join(fp, f'{key}.qza')
            artifacts[key], error = _load_input_file(artifact_path)

            if error:
                return None, error

    return artifacts, None


def _load_unordered_collection(fp):
    import os

    artifacts = {}

    for artifact in os.listdir(fp):
        artifact_fp = os.path.join(fp, artifact)
        artifacts[artifact], error = _load_input_file(artifact_fp)

        if error:
            return None, error

    return artifacts, None


def _load_input_cache(fp):
    artifact = error = None
    try:
        artifact = try_as_cache_input(fp)
    except Exception as e:
        error = e

    return artifact, error


def _load_input_file(fp):
    import qiime2.sdk

    # test if valid
    peek = None
    try:
        peek = qiime2.sdk.Result.peek(fp)
    except Exception as error:
        if isinstance(error, SyntaxError):
            raise error
        # ideally ValueError: X is not a QIIME archive.
        # but sometimes SyntaxError or worse
        return None, error

    # try to actually load
    try:
        artifact = qiime2.sdk.Result.load(fp)
        return artifact, None

    except Exception as e:
        if peek:
            # abort early as there's nothing else to do
            raise ValueError(
                "It looks like you have an Artifact but are missing the"
                " plugin(s) necessary to load it. Artifact has type"
                f" {peek.type!r} and format {peek.format!r}") from e
        else:
            error = e

        return None, error


def try_as_cache_input(fp):
    """ Determine if an input is in a cache and load it from the cache if it is
    """
    import os
    from qiime2 import Cache

    cache_path, key = _get_cache_path_and_key(fp)

    # We don't want to invent a new cache on disk here because if their input
    # exists their cache must also already exist
    if not os.path.exists(cache_path) or not Cache.is_cache(cache_path):
        raise ValueError(f"The path {cache_path!r} is not a valid cache.")

    cache = Cache(cache_path)
    return cache.load(key)


def _get_cache_path_and_key(fp):
    return fp.rsplit(':', 1)


def _get_path_and_collection_key(fp):
    return fp.split(':', 1)


def get_default_recycle_pool(plugin_action):
    from hashlib import sha1

    return f'recycle_{plugin_action}_' \
           f'{sha1(plugin_action.encode("utf-8")).hexdigest()}'
