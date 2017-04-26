# ----------------------------------------------------------------------------
# Copyright (c) 2016-2017, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import collections

import click

import q2cli.dev
import q2cli.info
import q2cli.tools


class RootCommand(click.MultiCommand):
    """This class defers to either the PluginCommand or the builtin cmds"""
    _builtin_commands = collections.OrderedDict([
        ('info', q2cli.info.info),
        ('tools', q2cli.tools.tools),
        ('dev', q2cli.dev.dev)
    ])

    def __init__(self, *args, **kwargs):
        import sys
        invalid = []
        unicodes = ["\u2018", "\u2019", "\u201C", "\u201D", "\u2014"]
        for command in sys.argv:
            if any(x in command for x in unicodes):
                invalid.append(command)
        if invalid:
            click.secho("Error: Detected invalid character in: %s\n"
                        "Verify the correct quotes or dashes (ASCII) are "
                        "being used." %
                        ', '.join(invalid), err=True, fg='red', bold=True)
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
            import q2cli.cache
            self._plugins = q2cli.cache.CACHE.plugins

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
            return None

        support = 'Getting user support: %s' % plugin['user_support_text']
        citing = 'Citing this plugin: %s' % plugin['citation_text']
        website = 'Plugin website: %s' % plugin['website']
        description = 'Description: %s' % plugin['description']
        help_ = '\n\n'.join([description, website, support, citing])

        return PluginCommand(plugin, name=name,
                             short_help=plugin['short_description'],
                             help=help_)


class PluginCommand(click.MultiCommand):
    """Provides ActionCommands based on available Actions"""
    def __init__(self, plugin, *args, **kwargs):
        import q2cli.util

        super().__init__(*args, **kwargs)
        # the cli currently doesn't differentiate between methods
        # and visualizers, it treats them generically as Actions
        self._plugin = plugin
        self._action_lookup = {q2cli.util.to_cli_name(id): a for id, a in
                               plugin['actions'].items()}

    def list_commands(self, ctx):
        return sorted(self._action_lookup)

    def get_command(self, ctx, name):
        try:
            action = self._action_lookup[name]
        except KeyError:
            click.echo("Error: QIIME 2 plugin %r has no action %r."
                       % (self._plugin['name'], name), err=True)
            ctx.exit(2)  # Match exit code of `return None`

        return ActionCommand(name, self._plugin, action)


class ActionCommand(click.Command):
    """A click manifestation of a QIIME 2 API Action (Method/Visualizer)

    The ActionCommand generates Handlers which map from 1 Action API parameter
    to one or more Click.Options.

    MetaHandlers are handlers which are not mapped to an API parameter, they
    are handled explicitly and generally return a `fallback` function which
    can be used to supplement value lookup in the regular handlers.
    """
    def __init__(self, name, plugin, action):
        import q2cli.handlers
        import q2cli.util

        self.plugin = plugin
        self.action = action
        self.generated_handlers = self.build_generated_handlers()
        self.verbose_handler = q2cli.handlers.VerboseHandler()
        self.quiet_handler = q2cli.handlers.QuietHandler()
        # Meta-Handlers:
        self.output_dir_handler = q2cli.handlers.OutputDirHandler()
        self.cmd_config_handler = q2cli.handlers.CommandConfigHandler(
            q2cli.util.to_cli_name(plugin['name']),
            q2cli.util.to_cli_name(self.action['id'])
        )
        super().__init__(name, params=list(self.get_click_parameters()),
                         callback=self, short_help=action['name'],
                         help=action['description'])

    def build_generated_handlers(self):
        import q2cli.handlers

        handlers = collections.OrderedDict()
        handler_map = collections.OrderedDict([
            ('inputs', q2cli.handlers.ArtifactHandler),
            ('parameters', q2cli.handlers.parameter_handler_factory),
            ('outputs', q2cli.handlers.ResultHandler)
        ])

        signature = self.action['signature']
        defaults = signature['defaults']

        for group_type, constructor in handler_map.items():
            grp = signature[group_type]

            for item in grp:
                name = item['name']
                default = defaults.get(name, q2cli.handlers.NoDefault)
                handlers[name] = constructor(default=default, **item)

        return handlers

    def get_click_parameters(self):
        # Handlers may provide more than one click.Option
        for handler in self.generated_handlers.values():
            yield from handler.get_click_options()

        # Meta-Handlers' Options:
        yield from self.output_dir_handler.get_click_options()
        yield from self.cmd_config_handler.get_click_options()

        yield from self.verbose_handler.get_click_options()
        yield from self.quiet_handler.get_click_options()

    def __call__(self, **kwargs):
        """Called when user hits return, **kwargs are Dict[click_names, Obj]"""
        import importlib
        import itertools
        import os
        import qiime2.util

        arguments, missing_in, verbose, quiet = self.handle_in_params(kwargs)
        outputs, missing_out = self.handle_out_params(kwargs)

        if missing_in or missing_out:
            # A new context is generated for a callback, which will result in
            # the ctx.command_path duplicating the action, so just use the
            # parent so we can print the help *within* a callback.
            ctx = click.get_current_context().parent
            click.echo(ctx.get_help()+"\n", err=True)
            for option in itertools.chain(missing_in, missing_out):
                click.secho("Error: Missing option: --%s" % option, err=True,
                            fg='red', bold=True)
            if missing_out:
                click.echo(_OUTPUT_OPTION_ERR_MSG, err=True)
            ctx.exit(1)

        module_path = 'qiime2.plugins.%s.actions' % self.plugin['id']
        actions_module = importlib.import_module(module_path)
        action = getattr(actions_module, self.action['id'])

        # `qiime2.util.redirected_stdio` defaults to stdout/stderr when
        # supplied `None`.
        log = None

        if not verbose:
            import tempfile
            log = tempfile.NamedTemporaryFile(prefix='qiime2-q2cli-err-',
                                              suffix='.log',
                                              delete=False, mode='w')

        cleanup_logfile = False
        try:
            with qiime2.util.redirected_stdio(stdout=log, stderr=log):
                results = action(**arguments)
        except Exception as e:
            import traceback
            if verbose:
                import sys
                traceback.print_exc(file=sys.stderr)
                click.echo(err=True)
                self._echo_plugin_error(e, 'See above for debug info.')
            else:
                traceback.print_exc(file=log)
                click.echo(err=True)
                self._echo_plugin_error(e, 'Debug info has been saved to %s.'
                                        % log.name)
            click.get_current_context().exit(1)
        else:
            cleanup_logfile = True
        finally:
            if log and cleanup_logfile:
                log.close()
                os.remove(log.name)

        if not quiet:
            for result, output in zip(results, outputs):
                path = result.save(output)
                click.secho('Saved %s to: %s' % (result.type, path),
                            fg='green')

    def _echo_plugin_error(self, exception, tail):
        import textwrap

        exception = textwrap.indent(
            '\n'.join(textwrap.wrap(str(exception))), '  ')
        click.secho(
            'Plugin error from %s:\n\n%s\n\n%s'
            % (q2cli.util.to_cli_name(self.plugin['name']), exception, tail),
            fg='red', bold=True, err=True)

    def handle_in_params(self, kwargs):
        import itertools
        import q2cli.handlers

        arguments = {}
        missing = []
        cmd_fallback = self.cmd_config_handler.get_value(kwargs)

        verbose = self.verbose_handler.get_value(kwargs, fallback=cmd_fallback)
        quiet = self.quiet_handler.get_value(kwargs, fallback=cmd_fallback)

        for item in itertools.chain(self.action['signature']['inputs'],
                                    self.action['signature']['parameters']):
            name = item['name']
            handler = self.generated_handlers[name]
            try:
                arguments[name] = handler.get_value(
                    kwargs, fallback=cmd_fallback
                )
            except q2cli.handlers.ValueNotFoundException:
                missing += handler.missing

        return arguments, missing, verbose, quiet

    def handle_out_params(self, kwargs):
        import q2cli.handlers

        outputs = []
        missing = []
        cmd_fallback = self.cmd_config_handler.get_value(kwargs)
        out_fallback = self.output_dir_handler.get_value(
            kwargs, fallback=cmd_fallback
        )

        def fallback(*args):
            try:
                return cmd_fallback(*args)
            except q2cli.handlers.ValueNotFoundException:
                return out_fallback(*args)

        for item in self.action['signature']['outputs']:
            name = item['name']
            handler = self.generated_handlers[name]

            try:
                outputs.append(handler.get_value(kwargs, fallback=fallback))
            except q2cli.handlers.ValueNotFoundException:
                missing += handler.missing

        return outputs, missing


_OUTPUT_OPTION_ERR_MSG = """\
Note: When only providing names for a subset of the output Artifacts or
Visualizations, you must specify an output directory through use of the
--output-dir DIRECTORY flag.\
"""
