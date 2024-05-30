# ----------------------------------------------------------------------------
# Copyright (c) 2016-2023, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

from qiime2.core.cache import Cache


# Do not make this the default cache. If this is the default cache then we will
# instantiate the default cache when the module is imported which will write a
# process pool to the default cache which is undesirable if that isn't the
# cache we will be using for this action
_USED_ARTIFACT_CACHE = None


def set_used_artifact_cache(args):
    """Validates that the args passed in actually contain a valid path to an
    existing cache following the --use-cache argument and if so sets that cache
    as the used cache for this invocation.

    Parameters
    ----------
    args : List[str]
        The arguments provided on the cli to this QIIME 2 invocation/

    NOTES
    -----
    Should only be called if --use-cache is already known to be in the args
    provided.

    Should only be called once to init the used cache for this invocation.
    """
    from q2cli.util import exit_with_error

    global _USED_ARTIFACT_CACHE

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

    _USED_ARTIFACT_CACHE = Cache(cache_path)


def unset_used_artifact_cache():
    """Set the USED_ARTIFACT_CACHE back to None.
    """
    global _USED_ARTIFACT_CACHE

    _USED_ARTIFACT_CACHE = None


def get_used_artifact_cache():
    """If the used cache has been set then return it otherwise return the
    default cache. We use this getter because we don't want to instantiate the
    default cache unless that is the cache we are using. This is because if we
    instantiate the default cache we will put a process pool in it, and we want
    to avoid that unless necessary.

    Returns
    -------
    Cache
        The default cache if the user didn't set a cache or the cache they set
        if they did set one.
    """
    return Cache() if _USED_ARTIFACT_CACHE is None else _USED_ARTIFACT_CACHE
