# ----------------------------------------------------------------------------
# Copyright (c) 2016--, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------

import collections
import os
import tempfile

import click
import qiime
import qiime.plugin
import qiime.sdk
from qiime.sdk import PluginManager

from . import __version__ as q2cli_version


PLUGIN_MANAGER = PluginManager()


class QiimeCLI(click.MultiCommand):

    def list_commands(self, ctx):
        plugins = PLUGIN_MANAGER.plugins.keys()
        return sorted(plugins)

    def get_command(self, ctx, name):
        if name in PLUGIN_MANAGER.plugins:
            plugin = PLUGIN_MANAGER.plugins[name]

            class PluginCommand(click.MultiCommand):

                def list_commands(self, ctx):
                    # the cli currently doesn't differentiate between methods
                    # and visualizers.
                    commands = list(plugin.methods.keys()) + \
                               list(plugin.visualizers.keys())
                    return sorted(commands)

                def get_command(self, ctx, name):
                    if name in plugin.methods:
                        return _build_method_command(
                            name, plugin.methods[name])
                    else:
                        return _build_visualizer_command(
                            name, plugin.visualizers[name])

            return PluginCommand(ctx)
        else:
            return None


# Top-level option handlers

def _echo_version(ctx, name, value):
    if value:
        click.echo('QIIME version: %s' % qiime.__version__)
        click.echo('q2cli version: %s' % q2cli_version)


def _echo_plugins(ctx, name, value):
    if value:
        installed_plugins = PLUGIN_MANAGER.plugins
        if len(installed_plugins) == 0:
            click.echo('No plugins are currently installed.\nYou can browse '
                       'the official QIIME 2 plugins at: '
                       'https://github.com/qiime2.')
        else:
            click.echo('Installed plugins:')
            for name, plugin in installed_plugins.items():
                click.echo(' %s %s (%s)' %
                           (name, plugin.version, plugin.website))


def _echo_info(ctx, name, value):
    if value:
        _echo_version(ctx, None, True)
        _echo_plugins(ctx, None, True)


@click.command(cls=QiimeCLI, invoke_without_command=True,
               no_args_is_help=True)
@click.option('--version', is_flag=True, callback=_echo_version,
              help='Print the version and exit.', expose_value=False)
@click.option('--plugins', is_flag=True, callback=_echo_plugins,
              help='List installed plugins and exit.', expose_value=False)
@click.option('--info', is_flag=True, callback=_echo_info,
              help='Print system details and exit.', expose_value=False)
def cli():
    pass


def _build_method_callback(method):
    def f(ctx, **kwargs):
        # TODO remove hardcoding of extension pending
        # https://github.com/qiime2/qiime2/issues/59
        output_extension = '.qza'
        inputs = {
            ia_name: qiime.sdk.Artifact.load(kwargs[ia_name]) for ia_name in method.signature.inputs}
        parameters = {
            ip_name: kwargs[ip_name] for ip_name in method.signature.parameters}
        outputs = collections.OrderedDict()
        for oa_name in method.signature.outputs:
            oa_value = kwargs[oa_name]
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
        output_extension = '.qzv'
        inputs = {
            ia_name: qiime.sdk.Artifact.load(kwargs[ia_name]) for ia_name in visualizer.signature.inputs}
        parameters = {
            ip_name: kwargs[ip_name] for ip_name in visualizer.signature.parameters}
        outputs = collections.OrderedDict()
        for oa_name in visualizer.signature.outputs:
            oa_value = kwargs[oa_name]
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


def _build_input_option(name, type_):
    result = click.Option(['--%s' % name],
                          required=True,
                          type=click.Path(exists=True, dir_okay=False),
                          help='Input %s' % str(type_[0]))
    return result


def _build_parameter_option(name, type_):
    result = click.Option(['--%s' % name],
                          required=True,
                          type=type_[1])
    return result


def _build_output_option(name, type_):
    result = click.Option(['--%s' % name],
                          required=True,
                          type=click.Path(exists=False, dir_okay=False),
                          help='Output %s' % str(type_[0]))
    return result


def _build_method_command(name, method):
    parameters = []
    for ia_name, ia_type in method.signature.inputs.items():
        parameters.append(_build_input_option(ia_name, ia_type))
    for ip_name, ip_type in method.signature.parameters.items():
        parameters.append(_build_parameter_option(ip_name, ip_type))
    for oa_name, oa_type in method.signature.outputs.items():
        parameters.append(_build_output_option(oa_name, oa_type))

    callback = _build_method_callback(method)
    return click.Command(name, params=parameters, callback=callback)


def _build_visualizer_command(name, visualizer):
    parameters = []
    for ia_name, ia_type in visualizer.signature.inputs.items():
        parameters.append(_build_input_option(ia_name, ia_type))
    for ip_name, ip_type in visualizer.signature.parameters.items():
        parameters.append(_build_parameter_option(ip_name, ip_type))
    for oa_name, oa_type in visualizer.signature.outputs.items():
        parameters.append(_build_output_option(oa_name, oa_type))

    callback = _build_visualizer_callback(visualizer)
    return click.Command(name, params=parameters, callback=callback)


# cli entry point
def main():
    cli()
