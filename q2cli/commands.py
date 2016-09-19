# ----------------------------------------------------------------------------
# Copyright (c) 2016--, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------

import collections
import itertools

import click
import qiime.sdk

import q2cli.tools
import q2cli.info
import q2cli.handlers
import q2cli.util


class RootCommand(click.MultiCommand):
    """This class defers to either the PluginCommand or the builtin cmds"""
    _builtin_commands = {'tools': q2cli.tools.tools,
                         'info': q2cli.info.info}

    @property
    def _plugin_lookup(self):
        plugin_manager = qiime.sdk.PluginManager()
        name_map = {}
        for plugin_name, plugin in plugin_manager.plugins.items():
            if plugin.actions:
                name_map[q2cli.util.to_cli_name(plugin_name)] = plugin
        return name_map

    def list_commands(self, ctx):
        builtins = sorted(self._builtin_commands)
        plugins = sorted(self._plugin_lookup)
        return itertools.chain(builtins, plugins)

    def get_command(self, ctx, name):
        if name in self._builtin_commands:
            return self._builtin_commands[name]

        try:
            plugin = self._plugin_lookup[name]
        except KeyError:
            return None

        # TODO: pass short_help=plugin.description, pending its
        # existence: https://github.com/qiime2/qiime2/issues/81
        support = 'Getting user support: %s' % plugin.user_support_text
        citing = 'Citing this plugin: %s' % plugin.citation_text
        website = 'Plugin website: %s' % plugin.website
        help_ = '\n\n'.join([website, support, citing])

        return PluginCommand(plugin, ctx, short_help='', help=help_)


class PluginCommand(click.MultiCommand):
    """Provides ActionCommands based on available Actions"""
    def __init__(self, plugin, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # the cli currently doesn't differentiate between methods
        # and visualizers, it treats them generically as Actions
        self._plugin = plugin
        self._action_lookup = {q2cli.util.to_cli_name(k): v for k, v in
                               plugin.actions.items()}

    def list_commands(self, ctx):
        return sorted(self._action_lookup)

    def get_command(self, ctx, name):
        try:
            action = self._action_lookup[name]
        except KeyError:
            click.echo("Error: QIIME plugin %r has no action %r."
                       % (self._plugin.name, name), err=True)
            ctx.exit(2)  # Match exit code of `return None`

        return ActionCommand(name, self._plugin, action)


class ActionCommand(click.Command):
    """A click manifestation of a QIIME API Action (Method/Visualizer)

    The ActionCommand generates Handlers which map from 1 Action API parameter
    to one or more Click.Options.

    MetaHandlers are handlers which are not mapped to an API parameter, they
    are handled explicitly and generally return a `fallback` function which
    can be used to supplement value lookup in the regular handlers.
    """
    def __init__(self, name, plugin, action):
        self.action = action
        self.generated_handlers = self.build_generated_handlers()
        # Meta-Handlers:
        self.output_dir_handler = q2cli.handlers.OutputDirHandler()
        self.cmd_config_handler = q2cli.handlers.CommandConfigHandler(
            q2cli.util.to_cli_name(plugin.name),
            q2cli.util.to_cli_name(self.action.id)
        )
        super().__init__(name, params=list(self.get_click_parameters()),
                         callback=self, short_help=action.name,
                         help=action.description)

    def build_generated_handlers(self):
        handlers = collections.OrderedDict()
        handler_map = collections.OrderedDict([
            ('inputs', q2cli.handlers.ArtifactHandler),
            ('parameters', q2cli.handlers.parameter_handler_factory),
            ('outputs', q2cli.handlers.ResultHandler)
        ])

        for group_type, constructor in handler_map.items():
            grp = getattr(self.action.signature, group_type)
            # TODO Update order of inputs and parameters to match
            # `Action.signature` when signature retains API order:
            # https://github.com/qiime2/qiime2/issues/70
            # (i.e. just remove the sorted call)
            defaults = self.action.signature.defaults
            for name, (semtype, _) in sorted(grp.items(), key=lambda x: x[0]):
                default = defaults.get(name, q2cli.handlers.NoDefault)
                handlers[name] = constructor(name, semtype, default)

        return handlers

    def get_click_parameters(self):
        # Handlers may provide more than one click.Option
        for handler in self.generated_handlers.values():
            yield from handler.get_click_options()

        # Meta-Handlers' Options:
        yield from self.output_dir_handler.get_click_options()
        yield from self.cmd_config_handler.get_click_options()

    def __call__(self, **kwargs):
        """Called when user hits return, **kwargs are Dict[click_names, Obj]"""
        arguments, missing_in = self.handle_in_params(kwargs)
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

        results = self.action(**arguments)
        if not isinstance(results, tuple):
            results = results,

        for result, output in zip(results, outputs):
            if not output.endswith(result.extension):
                output += result.extension
            result.save(output)

    def handle_in_params(self, kwargs):
        arguments = {}
        missing = []
        cmd_fallback = self.cmd_config_handler.get_value(kwargs)

        for name in itertools.chain(self.action.signature.inputs,
                                    self.action.signature.parameters):
            handler = self.generated_handlers[name]
            try:
                arguments[name] = handler.get_value(
                    kwargs, fallback=cmd_fallback
                )
            except q2cli.handlers.ValueNotFoundException:
                missing += handler.missing

        return arguments, missing

    def handle_out_params(self, kwargs):
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

        for name in self.action.signature.outputs:
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
