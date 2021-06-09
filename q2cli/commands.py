# ----------------------------------------------------------------------------
# Copyright (c) 2016-2021, QIIME 2 development team.
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
            q2cli.util.citations_option(self._get_citation_records)
        ]

        super().__init__(name, *args, short_help=plugin['short_description'],
                         help=help_, params=params, **kwargs)

    def _get_version(self, ctx, param, value):
        if not value or ctx.resilient_parsing:
            return

        import qiime2.sdk
        for entrypoint in qiime2.sdk.PluginManager.iter_entry_points():
            plugin = entrypoint.load()
            if (self._plugin['name'] == plugin.name):
                pkg_name = entrypoint.dist.project_name
                pkg_version = entrypoint.dist.version
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
        import qiime2.sdk
        pm = qiime2.sdk.PluginManager()
        return pm.plugins[self._plugin['name']].citations

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
            q2cli.util.usage_example_option(self._get_action),
            q2cli.util.citations_option(self._get_citation_records)
        ]

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

    def _get_action(self):
        import qiime2.sdk
        pm = qiime2.sdk.PluginManager()
        plugin = pm.plugins[self.plugin['name']]
        return plugin.actions[self.action['id']]

    def __call__(self, **kwargs):
        """Called when user hits return, **kwargs are Dict[click_names, Obj]"""
        import os
        import qiime2.util

        output_dir = kwargs.pop('output_dir')
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
            path = result.save(output)
            if not quiet:
                click.echo(
                    CONFIG.cfg_style('success', 'Saved %s to: %s' %
                                     (result.type, path)))

    def _order_outputs(self, outputs):
        ordered = []
        for item in self.action['signature']:
            if item['type'] == 'output':
                ordered.append(outputs[item['name']])
        return ordered
