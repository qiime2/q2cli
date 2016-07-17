# ----------------------------------------------------------------------------
# Copyright (c) 2016--, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------

import os
import collections

import click
import qiime
import qiime.plugin
import qiime.sdk
from qiime.sdk import PluginManager

import q2cli._tools
import q2cli._info


class QiimeCLI(click.MultiCommand):

    _plugin_manager = PluginManager()
    _builtin_commands = {'tools': q2cli._tools.tools,
                         'info': q2cli._info.info}

    @property
    def _name_map(self):
        name_map = {}
        for plugin_name, plugin in self._plugin_manager.plugins.items():
            if plugin.methods or plugin.visualizers:
                name_map[_name_to_command(plugin_name)] = plugin_name
        return name_map

    def list_commands(self, ctx):
        builtins = list(sorted(self._builtin_commands.keys()))
        plugins = sorted(list(self._name_map))
        return builtins + plugins

    def get_command(self, ctx, name):
        if name in self._builtin_commands:
            return self._builtin_commands[name]
        name_map = self._name_map
        if name in name_map:
            plugin_name = name_map[name]
            plugin = self._plugin_manager.plugins[plugin_name]

            class PluginCommand(click.MultiCommand):
                @property
                def _name_map(self):
                    # the cli currently doesn't differentiate between methods
                    # and visualizers.
                    return {_name_to_command(k): k for k in
                            list(plugin.methods) +
                            list(plugin.visualizers)}

                def list_commands(self, ctx):
                    return sorted(self._name_map)

                def get_command(self, ctx, name):
                    name_map = self._name_map
                    if name not in name_map:
                        click.echo(("%s is not a valid command for plugin "
                                    "%s.") % (name, plugin.name), err=True)
                        ctx.exit(1)
                    action_name = name_map[name]
                    if action_name in plugin.methods:
                        return _build_method_command(
                            name, plugin.methods[action_name])
                    else:
                        return _build_visualizer_command(
                            name, plugin.visualizers[action_name])
            # TODO: pass help=plugin.description, pending its existence:
            # https://github.com/qiime2/qiime2/issues/81
            return PluginCommand(ctx)
        else:
            return None


@click.command(cls=QiimeCLI, invoke_without_command=True, no_args_is_help=True)
@click.option('--version', is_flag=True, callback=q2cli._info._echo_version,
              help='Print the version and exit.', expose_value=False)
def cli():
    pass


def _build_parameter(name, type_, options):
    if type_[0] is qiime.plugin.Metadata:
        metadata = qiime.Metadata.load(options['%s_file' % name])
        return metadata
    elif type_[0] is qiime.plugin.MetadataCategory:
        metadata_category = qiime.MetadataCategory.load(
            options['%s_file' % name],
            options['%s_category' % name])
        return metadata_category
    else:
        return options[name]


def _build_method_callback(method):
    def f(ctx, **kwargs):
        # TODO remove hardcoding of extension pending
        # https://github.com/qiime2/qiime2/issues/59
        name_map = _get_api_names_from_option_names(kwargs)
        output_extension = '.qza'
        inputs = {
            ia_name: qiime.sdk.Artifact.load(name_map[ia_name])
            for ia_name in method.signature.inputs}
        parameters = {}
        for ip_name, ip_type in method.signature.parameters.items():
            parameters[ip_name] = _build_parameter(ip_name, ip_type, kwargs)
        outputs = collections.OrderedDict()
        for oa_name in method.signature.outputs:
            oa_value = name_map[oa_name]
            file_extension = os.path.splitext(oa_value)[1]
            if file_extension != output_extension:
                oa_value = ''.join([oa_value, output_extension])
            outputs[oa_name] = oa_value
        args = inputs
        args.update(parameters)
        output_artifacts = method(**args)
        if type(output_artifacts) is not tuple:
            output_artifacts = (output_artifacts,)

        for output_artifact, output_filepath in zip(output_artifacts,
                                                    outputs.values()):
            output_artifact.save(output_filepath)

    return click.pass_context(f)


def _build_visualizer_callback(visualizer):
    # TODO there is a lot of code duplicated between
    # _build_visualizer_callback and _build_method_callback - revisit
    # this after the refactoring that is happening as part of
    # https://github.com/qiime2/qiime2/issues/39
    def f(ctx, **kwargs):
        # TODO remove hardcoding of extension pending
        # https://github.com/qiime2/qiime2/issues/59
        name_map = _get_api_names_from_option_names(kwargs)
        output_extension = '.qzv'
        inputs = {
            ia_name: qiime.sdk.Artifact.load(name_map[ia_name])
            for ia_name in visualizer.signature.inputs}
        parameters = {}
        for ip_name, ip_type in visualizer.signature.parameters.items():
            parameters[ip_name] = _build_parameter(ip_name, ip_type, kwargs)
        outputs = collections.OrderedDict()
        for oa_name in visualizer.signature.outputs:
            oa_value = name_map[oa_name]
            file_extension = os.path.splitext(oa_value)[1]
            if file_extension != output_extension:
                oa_value = ''.join([oa_value, output_extension])
            outputs[oa_name] = oa_value
        args = inputs
        args.update(parameters)
        output_visualizations = visualizer(**args)
        if type(output_visualizations) is not tuple:
            output_visualizations = (output_visualizations,)

        for output_visualization, output_filepath in zip(output_visualizations,
                                                         outputs.values()):
            output_visualization.save(output_filepath)

    return click.pass_context(f)


def _name_to_command(name):
    return name.replace('_', '-')


def _build_input_option(name, type_):
    name = _name_to_command(name)
    result = click.Option(['--i-%s' % name],
                          required=True,
                          type=click.Path(exists=True, dir_okay=False),
                          help='Input %s' % str(type_[0]))
    return result


def _build_parameter_option(name, type_):
    name = _name_to_command(name)
    results = []
    ast = type_[0].to_ast()
    if type_[1] is qiime.MetadataCategory:
        results.append(click.Option(
            ['--%s-file' % name],
            required=True,
            type=click.Path(exists=True, dir_okay=False),
            help='Sample metadata mapping file'))
        results.append(click.Option(
            ['--%s-category' % name],
            required=True,
            type=click.STRING,
            help='Category from sample metadata mapping file'))
    elif type_[1] is qiime.Metadata:
        results.append(click.Option(
            ['--%s-file' % name],
            required=True,
            type=click.Path(exists=True, dir_okay=False),
            help='Sample metadata mapping file'))
    elif 'choices' in ast['predicate']:
        results.append(click.Option(
            ['--%s' % name],
            required=True,
            type=click.Choice(sorted(ast['predicate']['choices']))))
    else:
        results.append(click.Option(
            ['--%s' % name],
            required=True,
            type=type_[1]))
    return results


def _build_output_option(name, type_):
    name = _name_to_command(name)
    result = click.Option(
        ['--o-%s' % name],
        required=True,
        type=click.Path(exists=False, dir_okay=False),
        help='Output %s' % str(type_[0]))
    return result


def _build_method_command(name, method):
    parameters = []
    for ia_name, ia_type in method.signature.inputs.items():
        parameters.append(_build_input_option(ia_name, ia_type))
    for ip_name, ip_type in method.signature.parameters.items():
        parameters.extend(_build_parameter_option(ip_name, ip_type))
    for oa_name, oa_type in method.signature.outputs.items():
        parameters.append(_build_output_option(oa_name, oa_type))

    callback = _build_method_callback(method)
    return click.Command(name, params=parameters, callback=callback,
                         short_help=method.name,
                         help=method.description)


def _build_visualizer_command(name, visualizer):
    parameters = []
    for ia_name, ia_type in visualizer.signature.inputs.items():
        parameters.append(_build_input_option(ia_name, ia_type))
    for ip_name, ip_type in visualizer.signature.parameters.items():
        parameters.extend(_build_parameter_option(ip_name, ip_type))
    for oa_name, oa_type in visualizer.signature.outputs.items():
        parameters.append(_build_output_option(oa_name, oa_type))

    callback = _build_visualizer_callback(visualizer)
    return click.Command(name, params=parameters, callback=callback,
                         short_help=visualizer.name,
                         help=visualizer.description)


def _get_api_names_from_option_names(option_names):
        option_name_map = {}
        for key in option_names:
            if key.startswith('i_') or key.startswith('o_'):
                stripped_key = key[2:]
                option_name_map[stripped_key] = option_names[key]
        return option_name_map


# cli entry point
def main():
    cli()
