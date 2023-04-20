# ----------------------------------------------------------------------------
# Copyright (c) 2016-2023, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import click

import q2cli.builtin.dev
import q2cli.builtin.info
import q2cli.builtin.tools

from q2cli.click.command import BaseCommandMixin
from q2cli.core.config import CONFIG


class RootCommand(BaseCommandMixin, click.MultiCommand):
    """This class defers to either the PluginCommand or the builtin cmds"""
    _builtin_commands = {
        'info': q2cli.builtin.info.info,
        'tools': q2cli.builtin.tools.tools,
        'dev': q2cli.builtin.dev.dev
    }

    def __init__(self, *args, **kwargs):
        import re
        import sys

        unicodes = ["\u2018", "\u2019", "\u201C", "\u201D", "\u2014", "\u2013"]
        category_regex = re.compile(r'--m-(\S+)-category')

        invalid_chars = []
        categories = []
        for command in sys.argv:
            if any(x in command for x in unicodes):
                invalid_chars.append(command)

            match = category_regex.fullmatch(command)
            if match is not None:
                param_name, = match.groups()
                # Maps old-style option name to new name.
                categories.append((command, '--m-%s-column' % param_name))

        if invalid_chars or categories:
            if invalid_chars:
                msg = ("Error: Detected invalid character in: %s\nVerify the "
                       "correct quotes or dashes (ASCII) are being used."
                       % ', '.join(invalid_chars))
                click.echo(CONFIG.cfg_style('error', msg), err=True)
            if categories:
                old_to_new_names = '\n'.join(
                    'Instead of %s, trying using %s' % (old, new)
                    for old, new in categories)
                msg = ("Error: The following options no longer exist because "
                       "metadata *categories* are now called metadata "
                       "*columns* in QIIME 2.\n\n%s" % old_to_new_names)
                click.echo(CONFIG.cfg_style('error', msg), err=True)
            sys.exit(-1)

        super().__init__(*args, **kwargs)

        # Plugin state for current deployment that will be loaded from cache.
        # Used to construct the dynamic CLI.
        self._plugins = None

    @property
    def _plugin_lookup(self):
        import q2cli.util

        # See note in `q2cli.completion.write_bash_completion_script` for why
        # `self._plugins` will not always be obtained from
        # `q2cli.cache.CACHE.plugins`.
        if self._plugins is None:
            import q2cli.core.cache
            self._plugins = q2cli.core.cache.CACHE.plugins

        name_map = {}
        for name, plugin in self._plugins.items():
            if plugin['actions']:
                name_map[q2cli.util.to_cli_name(name)] = plugin
        return name_map

    def list_commands(self, ctx):
        import itertools

        # Avoid sorting builtin commands as they have a predefined order based
        # on applicability to users. For example, it isn't desirable to have
        # the `dev` command listed before `info` and `tools`.
        builtins = self._builtin_commands
        plugins = sorted(self._plugin_lookup)
        return itertools.chain(builtins, plugins)

    def get_command(self, ctx, name):
        if name in self._builtin_commands:
            return self._builtin_commands[name]

        try:
            plugin = self._plugin_lookup[name]
        except KeyError:
            from q2cli.util import get_close_matches

            possibilities = get_close_matches(name, self._plugin_lookup)
            if len(possibilities) == 1:
                hint = '  Did you mean %r?' % possibilities[0]
            elif possibilities:
                hint = '  (Possible commands: %s)' % ', '.join(possibilities)
            else:
                hint = ''

            click.echo(
                CONFIG.cfg_style('error', "Error: QIIME 2 has no "
                                 "plugin/command named %r." % name + hint),
                err=True)
            ctx.exit(2)  # Match exit code of `return None`

        return PluginCommand(plugin, name)


class PluginCommand(BaseCommandMixin, click.MultiCommand):
    """Provides ActionCommands based on available Actions"""
    def __init__(self, plugin, name, *args, **kwargs):
        import q2cli.util

        # the cli currently doesn't differentiate between methods
        # and visualizers, it treats them generically as Actions
        self._plugin = plugin
        self._action_lookup = {q2cli.util.to_cli_name(id): a for id, a in
                               plugin['actions'].items()}

        support = 'Getting user support: %s' % plugin['user_support_text']
        website = 'Plugin website: %s' % plugin['website']
        description = 'Description: %s' % plugin['description']
        help_ = '\n\n'.join([description, website, support])

        params = [
            click.Option(('--version',), is_flag=True, expose_value=False,
                         is_eager=True, callback=self._get_version,
                         help='Show the version and exit.'),
            q2cli.util.example_data_option(self._get_plugin),
            q2cli.util.citations_option(self._get_citation_records)
        ]

        super().__init__(name, *args, short_help=plugin['short_description'],
                         help=help_, params=params, **kwargs)

    def _get_version(self, ctx, param, value):
        if not value or ctx.resilient_parsing:
            return

        import q2cli.util
        pm = q2cli.util.get_plugin_manager()
        for plugin in pm.plugins.values():
            if (self._plugin['name'] == plugin.name):
                pkg_name = plugin.project_name
                pkg_version = plugin.version
                break
        else:
            pkg_name = pkg_version = "[UNKNOWN]"

        click.echo(
            "QIIME 2 Plugin '%s' version %s (from package '%s' version %s)"
            % (self._plugin['name'], self._plugin['version'],
               pkg_name, pkg_version)
        )
        ctx.exit()

    def _get_citation_records(self):
        import q2cli.util
        pm = q2cli.util.get_plugin_manager()
        return pm.plugins[self._plugin['name']].citations

    def _get_plugin(self):
        import q2cli.util
        pm = q2cli.util.get_plugin_manager()
        return pm.plugins[self._plugin['name']]

    def list_commands(self, ctx):
        return sorted(self._action_lookup)

    def get_command(self, ctx, name):
        try:
            action = self._action_lookup[name]
        except KeyError:
            from q2cli.util import get_close_matches

            possibilities = get_close_matches(name, self._action_lookup)
            if len(possibilities) == 1:
                hint = '  Did you mean %r?' % possibilities[0]
            elif possibilities:
                hint = '  (Possible commands: %s)' % ', '.join(possibilities)
            else:
                hint = ''

            click.echo(
                CONFIG.cfg_style('error', "Error: QIIME 2 plugin %r has no "
                                 "action %r." % (self._plugin['name'], name) +
                                 hint), err=True)
            ctx.exit(2)  # Match exit code of `return None`

        return ActionCommand(name, self._plugin, action)


class ActionCommand(BaseCommandMixin, click.Command):
    """A click manifestation of a QIIME 2 API Action (Method/Visualizer)

    """
    def __init__(self, name, plugin, action):
        import q2cli.util
        import q2cli.click.type

        self.plugin = plugin
        self.action = action

        self._inputs, self._params, self._outputs = \
            self._build_generated_options()

        self._misc = [
            click.Option(['--output-dir'],
                         type=q2cli.click.type.OutDirType(),
                         help='Output unspecified results to a directory'),
            click.Option(['--verbose / --quiet'], default=None, required=False,
                         help='Display verbose output to stdout and/or stderr '
                              'during execution of this action. Or silence '
                              'output if execution is successful (silence is '
                              'golden).'),
            click.Option(['--parsl'], is_flag=True, required=False,
                         help='Indicate that you want to execute your action '
                              'with parsl. This flag will check the following '
                              'locations for a parsl config file then load a '
                              'vendored default config located at X if it '
                              'does not find a config elsewhere.'),
            click.Option(['--parsl-config'], required=False,
                         type=click.Path(exists=True, dir_okay=False),
                         help='Indicate that you want to execute your action '
                              'with parsl using a config at the indicated '
                              'path.'),
            q2cli.util.example_data_option(
                self._get_plugin, self.action['id']),
            q2cli.util.citations_option(self._get_citation_records)
        ]

        # If this aciton is a pipeline it needs the --recycle and --no-recycle
        # options.
        action_obj = self._get_action()
        if action_obj.type == 'pipeline':
            self._misc.extend([
                click.Option(['--recycle'], required=False,
                             type=str,
                             help='Allows you to specify a pool to use for '
                                  'pipeline resumption. If you run a pipeline '
                                  'without this parameter or the --no-recycle '
                                  'flag, QIIME will default to the pool '
                                  'recycle_<plugin>_<action>_<sha1> of '
                                  '"plugin_action">'),
                click.Option(['--no-recycle'], is_flag=True, required=False,
                             help='Specifies that you do not want to attempt '
                                  'to recycle results from a previous failed '
                                  'pipeline run.'),
                click.Option(['--use-cache'], required=False,
                             type=click.Path(exists=True, file_okay=False),
                             help='Allows you to specify a cache to be used '
                                  'for pipeline resumption. Otherwise the '
                                  'default cache under /$TMP/qiime2/<uname> '
                                  'will be used.')])

        options = [*self._inputs, *self._params, *self._outputs, *self._misc]
        help_ = [action['description']]
        if self.action['deprecated']:
            help_.append(CONFIG.cfg_style(
                'warning', 'WARNING:\n\nThis command is deprecated and will '
                           'be removed in a future version of this plugin.'))
        super().__init__(name, params=options, callback=self,
                         short_help=action['name'], help='\n\n'.join(help_))

    def _build_generated_options(self):
        import q2cli.click.option

        inputs = []
        params = []
        outputs = []

        for item in self.action['signature']:
            item = item.copy()
            type = item.pop('type')

            if type == 'input':
                storage = inputs
            elif type == 'parameter':
                storage = params
            else:
                storage = outputs

            opt = q2cli.click.option.GeneratedOption(prefix=type[0], **item)
            storage.append(opt)

        return inputs, params, outputs

    def get_opt_groups(self, ctx):
        return {
            'Inputs': self._inputs,
            'Parameters': self._params,
            'Outputs': self._outputs,
            'Miscellaneous': self._misc + [self.get_help_option(ctx)]
        }

    def _get_citation_records(self):
        return self._get_action().citations

    def _get_plugin(self):
        import q2cli.util
        pm = q2cli.util.get_plugin_manager()
        return pm.plugins[self.plugin['name']]

    def _get_action(self):
        plugin = self._get_plugin()
        return plugin.actions[self.action['id']]

    def __call__(self, **kwargs):
        """Called when user hits return, **kwargs are Dict[click_names, Obj]"""
        import os

        import qiime2.util
        from q2cli.util import (output_in_cache, _get_cache_path_and_key,
                                get_default_recycle_pool)
        from qiime2.core.cache import Cache
        from qiime2.sdk import ResultCollection

        output_dir = kwargs.pop('output_dir')
        # If they gave us a cache and key combo as an output dir, we want to
        # error out, so we check if their output dir contains a : and the part
        # before it is a cache
        if output_dir:
            potential_cache = output_dir.rsplit(':', 1)[0]
            if potential_cache and os.path.exists(potential_cache) and \
                    Cache.is_cache(potential_cache):
                raise ValueError(f"The given output dir '{output_dir}' "
                                 "appears to be a cache:key combo. Cache keys "
                                 "cannot be used as output dirs.")

        # Args pertaining to pipeline resumption
        recycle = kwargs.pop('recycle', None)
        no_recycle = kwargs.pop('no_recycle', False)
        used_cache = kwargs.pop('use_cache', None)

        if recycle is not None and no_recycle:
            raise ValueError('Cannot set a pool to be used for recycling and '
                             'no recycle simultaneously.')

        parsl = kwargs.pop('parsl', False)
        parsl_config_fp = kwargs.pop('parsl_config', None)

        if parsl and parsl_config_fp is not None:
            raise ValueError('Cannot use both --parsl and --parsl-config. '
                             'Use --parsl if you want to use a parsl config '
                             'at a pre-defined location or the vendorered '
                             'default. Use --parsl-config if you want to pass '
                             'in a path to a parsl config.')

        if parsl_config_fp is not None:
            parsl = True

        verbose = kwargs.pop('verbose')
        if verbose is None:
            verbose = False
            quiet = False
        elif verbose:
            quiet = False
        else:
            quiet = True

        arguments = {}
        init_outputs = {}
        for key, value in kwargs.items():
            prefix, *parts = key.split('_')
            key = '_'.join(parts)

            if prefix == 'o':
                if value is None:
                    value = os.path.join(output_dir, key)
                init_outputs[key] = value
            elif prefix == 'm':
                arguments[key[:-len('_file')]] = value
            else:
                arguments[key] = value

        outputs = self._order_outputs(init_outputs)
        action = self._get_action()

        # If --no-recycle is not set, pipelines attempt to recycle their
        # outputs from a pool by default allowing recovery of failed pipelines
        # from point of failure without needing to restart the pipeline from
        # the beginning
        recycle_pool = None
        if not no_recycle and action.type == 'pipeline':
            # We implicitly use a pool named
            # recycle_<plugin>_<action>_sha1(plugin_action) if no pool is
            # provided
            if recycle is None:
                plugin_acton = f'{action.plugin_id}_{action.id}'
                recycle_pool = get_default_recycle_pool(plugin_acton)
            # Otherwise we use the pool they said to use with the --recycle
            # argument
            else:
                recycle_pool = recycle

        # `qiime2.util.redirected_stdio` defaults to stdout/stderr when
        # supplied `None`.
        log = None

        if not verbose:
            import tempfile
            log = tempfile.NamedTemporaryFile(prefix='qiime2-q2cli-err-',
                                              suffix='.log',
                                              delete=False, mode='w')
        if action.deprecated:
            # We don't need to worry about redirecting this, since it should a)
            # always be shown to the user and b) the framework-originated
            # FutureWarning will wind up in the log file in quiet mode.

            msg = ('Plugin warning from %s:\n\n%s is deprecated and '
                   'will be removed in a future version of this plugin.' %
                   (q2cli.util.to_cli_name(self.plugin['name']), self.name))
            click.echo(CONFIG.cfg_style('warning', msg))

        cleanup_logfile = False
        try:
            with qiime2.util.redirected_stdio(stdout=log, stderr=log):
                if parsl:
                    action = action.parsl

                if recycle_pool is None:
                    results = action(**arguments)
                else:
                    if used_cache is not None and not \
                            Cache.is_cache(used_cache):
                        raise ValueError(f"The path '{used_cache}' is not a "
                                         "valid cache, please supply a path "
                                         "to a valid pre-existing cache.")

                    cache = Cache(path=used_cache)
                    pool = cache.create_pool(key=recycle_pool, reuse=True)
                    with pool:
                        results = action(**arguments)
        except Exception as e:
            header = ('Plugin error from %s:'
                      % q2cli.util.to_cli_name(self.plugin['name']))
            if verbose:
                # log is not a file
                log = 'stderr'
            q2cli.util.exit_with_error(e, header=header, traceback=log)
        else:
            cleanup_logfile = True
        finally:
            # OS X will reap temporary files that haven't been touched in
            # 36 hours, double check that the log is still on the filesystem
            # before trying to delete. Otherwise this will fail and the
            # output won't be written.
            if log and cleanup_logfile and os.path.exists(log.name):
                log.close()
                os.remove(log.name)

        if output_dir is not None:
            os.makedirs(output_dir)

        for result, output in zip(results, outputs):
            # TODO: Having a collection output causes this to become a tuple
            # for some reason. I don't understand why yet
            if isinstance(output, tuple) and len(output) == 1:
                output = output[0]

            if output_in_cache(output) and output_dir is None:
                cache_path, key = _get_cache_path_and_key(output)
                cache = Cache(cache_path)

                if isinstance(result, ResultCollection):
                    cache.save_collection(result, key)
                    path = output
                else:
                    cache.save(result, key)
                    path = output
            else:
                path = result.save(output)

            if not quiet:

                if isinstance(result, ResultCollection):
                    type = f'Collection[{list(result.values())[0].type}]'
                else:
                    type = result.type
                click.echo(
                    CONFIG.cfg_style('success', 'Saved %s to: %s' %
                                     (type, path)))

        # If we used a default recycle pool for a pipeline and the pipeline
        # succeeded, then we need to clean up the pool. Make sure to do this at
        # the very end so if a failure happens during writing results we still
        # have them
        if recycle_pool is not None and recycle is None:
            cache.remove(recycle_pool)

    def _order_outputs(self, outputs):
        ordered = []
        for item in self.action['signature']:
            if item['type'] == 'output':
                ordered.append(outputs[item['name']])
        return ordered

    def format_epilog(self, ctx, formatter):
        if self.action['epilog']:
            with formatter.section(click.style('Examples', bold=True)):
                for line in self.action['epilog']:
                    formatter.write(' ' * formatter.current_indent)
                    formatter.write(line)
                    formatter.write('\n')
