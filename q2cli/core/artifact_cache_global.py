# ----------------------------------------------------------------------------
# Copyright (c) 2016-2023, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

from qiime2.core.cache import Cache


# Init this to the default temp cache
USED_ARTIFACT_CACHE = Cache()


def set_used_artifact_cache(args):
    """Validates that the args passed in actually contain a valid path to an
    existing cache following the --use-cache argument and if so sets that cache
    as the used cache for this invocation.

    Parameters
    ----------
    args : List[str]
        The arguments provided on the cli to this QIIME 2 invocation

    NOTES
    -----
    Should only be called if --use-cache is already known to be in the args
    provided.

    Should only be called once to init the used cache for this invocation.
    """
    from q2cli.util import exit_with_error

    global USED_ARTIFACT_CACHE

    use_cache_idx = args.index('--use-cache')

    # They need to provide some kind of arg to use_cache
    if len(args) < use_cache_idx + 2:
        exc = ValueError('--use-cache expected an argument but none was '
                         'provided.')
        exit_with_error(exc)

    cache_path = args[use_cache_idx + 1]

    # The arg given should be a path that points to an existing cache
    if not Cache.is_cache(cache_path):
        exc = ValueError('--use-cache expected a path to an existing cache as '
                         f"an argument but received '{cache_path}' which is "
                         'not a path to an existing cache.')
        exit_with_error(exc)

    USED_ARTIFACT_CACHE = Cache(cache_path)


def unset_used_artifact_cache():
    """Set the USED_ARTIFACT_CACHE back to the default cache.
    """
    global USED_ARTIFACT_CACHE

    USED_ARTIFACT_CACHE = Cache()
