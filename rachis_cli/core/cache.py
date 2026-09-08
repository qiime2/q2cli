# ----------------------------------------------------------------------------
# Copyright (c) 2016-2026, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------


class DeploymentCache:
    """Cached CLI state for a rachis deployment.

    In this context, a rachis deployment is the set of installed Python
    packages, including their exact versions, that register one or more rachis
    plugins. The exact version of rachis-cli is also included in the
    deployment.

    The deployment cache stores the current deployment's package names and
    versions in a requirements.txt file under the cache directory. This file is
    used to determine if the cache is outdated. If the cache is determined to
    be outdated, it will be refreshed based on the current deployment state.
    Thus, adding, removing, upgrading, or downgrading a plugin package or
    rachis-cli itself will trigger a cache refresh.

    Two mechanisms are provided to force a cache refresh. Setting the
    environment variable RACHISCLIDEV (or the historical Q2CLIDEV) to any
    value will cause the cache to be refreshed upon instantiation. Calling
    `.refresh()` will also refresh the cache. Forced refreshing of the cache
    is useful for plugin and/or rachis-cli developers who want their changes
    to take effect in the CLI without changing their package versions.

    Cached CLI state is stored in a state.json file under the cache directory.
    It is not a public file format and it is not versioned. rachis-cli is
    included as part of the rachis deployment so that the cached state can
    always be read (or recreated as necessary) by the currently installed
    version of rachis-cli.

    This class is intended to be a singleton because it is responsible for
    managing the on-disk cache. Having more than one instance managing the
    cache has the possibility of two instances clobbering the cache (e.g. in a
    multithreaded/multiprocessing situation). Also, having a single instance
    improves performance by only reading and/or refreshing the cache a
    single time during its lifetime. Having two instances could, for example,
    trigger two cache refreshes if RACHISCLIDEV is set. To support these
    use-cases, a module-level `CACHE` variable stores a single instance of
    this class.

    """

    # Public API

    def __init__(self):
        import os

        # Indicates if the cache has been refreshed. For performance purposes,
        # the cache is only refreshed a single time (at maximum) during the
        # object's lifetime. Thus, "hot reloading" isn't supported, but this
        # shouldn't be necessary for the CLI.
        self._refreshed = False

        self._cache_dir = self._get_cache_dir()

        # RACHISCLIDEV is the current name; Q2CLIDEV is historical
        # and remains supported. The two are interchangeable.
        refresh = 'RACHISCLIDEV' in os.environ or 'Q2CLIDEV' in os.environ
        self._state = self._get_cached_state(refresh=refresh)

    @property
    def plugins(self):
        """Decoded JSON object representing CLI state on a per-plugin basis."""
        return self._state['plugins']

    def refresh(self):
        """Trigger a forced refresh of the cache.

        If the cache has already been refreshed (either by this method or at
        some point during instantiation), this method is a no-op.

        """
        if not self._refreshed:
            self._state = self._get_cached_state(refresh=True)

    # Private API

    def _get_cache_dir(self):
        import os
        import rachis_cli.util

        cache_dir = rachis_cli.util.get_cache_dir()
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir

    def _get_cached_state(self, refresh):
        import json
        import os.path
        import rachis_cli.util

        current_requirements = self._get_current_requirements()
        state_path = os.path.join(self._cache_dir, 'state.json')
        # See note on `get_completion_path` for why knowledge of this path
        # exists in `rachis_cli.util` and not in this class.
        completion_path = rachis_cli.util.get_completion_path()

        # The cache must be refreshed in the following cases:

        # 1) We have been explicitly told to refresh.
        if refresh:
            self._cache_current_state(current_requirements)
        # 2) The current deployment requirements are different than the cached
        #    requirements.
        elif current_requirements != self._get_cached_requirements():
            self._cache_current_state(current_requirements)
        # 3) The cached state file does not exist.
        elif not os.path.exists(state_path):
            self._cache_current_state(current_requirements)
        # 4) The cached bash completion script does not exist.
        elif not os.path.exists(completion_path):
            self._cache_current_state(current_requirements)

        def decoder(obj):
            if obj.get('__q2type__', None) == 'set':
                return set(obj['value'])
            return obj

        # Now that the cache is up-to-date, read it.
        try:
            with open(state_path, 'r') as fh:
                return json.load(fh, object_hook=decoder)
        except json.JSONDecodeError:
            # 5) The cached state file can't be read as JSON.
            self._cache_current_state(current_requirements)
            with open(state_path, 'r') as fh:
                return json.load(fh, object_hook=decoder)

    # NOTE: The private methods below are all used internally within
    # `_get_cached_state`.

    def _get_current_requirements(self):
        """Includes installed versions of rachis_cli and rachis plugins."""
        import itertools
        import importlib.metadata
        import rachis_cli
        from rachis.core.util import in_test_mode

        reqs = {f'rachis_cli=={rachis_cli.__version__}'}

        # A distribution (i.e. Python package) can have multiple plugins, where
        # each plugin is its own entry point. A distribution's `Requirement` is
        # hashable, and the `set` is used to exclude duplicates. Thus, we only
        # gather the set of requirements for all installed Python packages
        # containing one or more plugins. It is not necessary to track
        # individual plugin names and versions in order to determine if the
        # cache is outdated.
        # Plugins are migrating from the `qiime2.plugins` entry point group
        # to `rachis.plugins`. Read both, so that the cache still invalidates
        # for plugins which have not migrated yet. This mirrors
        # `rachis.sdk.PluginManager.iter_entry_points`. A distribution that
        # declares both groups yields duplicate entry points, which the `set`
        # above collapses.
        for entry_point in itertools.chain(
                importlib.metadata.entry_points(group='rachis.plugins'),
                importlib.metadata.entry_points(group='qiime2.plugins')):
            if in_test_mode():
                if entry_point.name in ('dummy-plugin', 'other-plugin'):
                    reqs.add(f'{entry_point.name}=={entry_point.dist.version}')
            else:
                if entry_point.name not in ('dummy-plugin', 'other-plugin'):
                    reqs.add(f'{entry_point.name}=={entry_point.dist.version}')

        return reqs

    def _get_cached_requirements(self):
        import os.path

        path = os.path.join(self._cache_dir, 'requirements.txt')

        if not os.path.exists(path):
            # No cached requirements. The empty set will always trigger a cache
            # refresh because the current requirements will, at minimum,
            # contain rachis_cli.
            return set()
        else:
            with open(path, 'r') as fh:
                contents = fh.read()
            try:
                # Each line in the file is a different dep
                deps = set(contents.split('\n'))
                if '' in deps:
                    # Pop off the empty newline at the bottom of the file
                    deps.remove('')
                return deps
            except Exception:
                # Unreadable cached requirements, trigger a cache refresh.
                return set()

    def _cache_current_state(self, requirements):
        import json
        import os.path
        import click
        import rachis_cli.core.completion
        import rachis_cli.util

        click.secho(
            "rachis is caching your current deployment for improved "
            "performance. This may take a few moments and should only happen "
            "once per deployment.", fg='yellow', err=True)

        cache_dir = self._cache_dir
        state = self._get_current_state()

        path = os.path.join(cache_dir, 'state.json')

        class Q2JSONEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, set):
                    return {
                        '__q2type__': 'set',
                        'value': list(obj),
                    }
                return super().default(obj)

        with open(path, 'w') as fh:
            json.dump(state, fh, cls=Q2JSONEncoder)

        rachis_cli.core.completion.write_bash_completion_script(
            state['plugins'], rachis_cli.util.get_completion_path())

        # Write requirements file last because the above steps may raise errors
        # (e.g. a plugin can't be loaded in `_get_current_state`). If any part
        # of the cache writing fails, it needs to be refreshed the next time
        # the cache is accessed. The absence of a requirements file will
        # trigger this cache refresh, avoiding this bug:
        #     https://github.com/rachis-org/rachis-cli/issues/88
        path = os.path.join(cache_dir, 'requirements.txt')
        with open(path, 'w') as fh:
            for req in requirements:
                # `str(Requirement)` is the recommended way to format a
                # `Requirement` that can be read with `Requirement.parse`.
                fh.write(str(req))
                fh.write('\n')

        self._refreshed = True

    def _get_current_state(self):
        """Get current CLI state as an object that is serializable as JSON.

        WARNING: This method is very slow and should only be called when the
        cache needs to be refreshed.

        """
        import rachis_cli.util

        state = {
            'plugins': {}
        }

        plugin_manager = rachis_cli.util.get_plugin_manager()
        for name, plugin in plugin_manager.plugins.items():
            state['plugins'][name] = self._get_plugin_state(plugin)

        return state

    def _get_plugin_state(self, plugin):
        import rachis_cli.core.state

        state = rachis_cli.core.state.get_plugin_state(plugin)
        for id, action in plugin.actions.items():
            state['actions'][id]['epilog'] = self._get_action_epilog(action)

        return state

    def _get_action_epilog(self, action):
        import rachis_cli.core.usage

        lines = []
        for name, example in action.examples.items():
            use = rachis_cli.core.usage.CLIUsage()

            use.comment('### example: %s\n' % (name.replace('_', ' '),))
            example(use)
            use.recorder.append('')

            lines += use.recorder

        return lines


# Singleton. Import and use this instance as necessary.
CACHE = DeploymentCache()
