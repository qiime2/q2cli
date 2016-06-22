# ----------------------------------------------------------------------------
# Copyright (c) 2016--, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------

import tempfile

import click
import qiime
import qiime.plugin
from qiime.sdk import PluginManager, SubprocessExecutor

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
                    # the cli currently doesn't differentiate between workflows
                    # and visualizations
                    commands = list(plugin.workflows.keys()) + \
                               list(plugin.visualizations.keys())
                    return sorted(commands)

                def get_command(self, ctx, name):
                    if name in plugin.workflows:
                        return _build_workflow_command(
                            name, plugin.workflows[name])
                    else:
                        return _build_visualization_command(
                            name, plugin.visualizations[name])

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


def _build_workflow_callback(wf):
    def f(ctx, **kwargs):
        # execute workflow
        executor = SubprocessExecutor()
        inputs = {
            ia_name: kwargs[ia_name] for ia_name in wf.signature.inputs}
        parameters = {
            ip_name: kwargs[ip_name] for ip_name in wf.signature.parameters}
        outputs = {
            oa_name: kwargs[oa_name] for oa_name in wf.signature.outputs
        }
        future_, _ = executor(wf, inputs, parameters, outputs)

        # block (i.e., wait) until result is ready
        completed_process = future_.result()

        if completed_process.returncode != 0:
            click.echo(completed_process.stdout)
            click.echo(completed_process.stderr, err=True)
            ctx.exit(completed_process.returncode)

    return click.pass_context(f)


def _build_visualization_callback(wf):
    # TODO there is a lot of code duplicated between
    # _build_visualization_callback and _build_workflow_callback - revisit
    # this after the refactoring that is happening as part of
    # https://github.com/qiime2/qiime2/issues/39
    def f(ctx, **kwargs):
        # TODO nest output_dir under user-configured temporary directory,
        # pending https://github.com/qiime2/qiime2/issues/12
        output_dir = tempfile.TemporaryDirectory()
        executor = SubprocessExecutor()
        inputs = {
            ia_name: kwargs[ia_name] for ia_name in wf.signature.inputs}
        parameters = {}
        for ip_name, ip_type in wf.signature.parameters.items():
            if ip_name == 'output_dir':
                parameters[ip_name] = output_dir.name
            else:
                parameters[ip_name] = kwargs[ip_name]
        outputs = {
            oa_name: kwargs[oa_name] for oa_name in wf.signature.outputs
        }
        future_, _ = executor(wf, inputs, parameters, outputs)

        # block (i.e., wait) until result is ready
        completed_process = future_.result()

        if completed_process.returncode != 0:
            click.echo(completed_process.stdout)
            click.echo(completed_process.stderr, err=True)
            ctx.exit(completed_process.returncode)

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


def _build_workflow_command(name, workflow):
    parameters = []
    for ia_name, ia_type in workflow.signature.inputs.items():
        parameters.append(_build_input_option(ia_name, ia_type))
    for ip_name, ip_type in workflow.signature.parameters.items():
        parameters.append(_build_parameter_option(ip_name, ip_type))
    for oa_name, oa_type in workflow.signature.outputs.items():
        parameters.append(_build_output_option(oa_name, oa_type))

    callback = _build_workflow_callback(workflow)
    return click.Command(name, params=parameters, callback=callback)


def _build_visualization_command(name, workflow):
    parameters = []
    for ia_name, ia_type in workflow.signature.inputs.items():
        parameters.append(_build_input_option(ia_name, ia_type))
    for ip_name, ip_type in workflow.signature.parameters.items():
        if ip_name == 'output_dir':
            # output_dir is a temporary directory used internally - we'll
            # create that and clean it up without the user knowing
            pass
        else:
            parameters.append(_build_parameter_option(ip_name, ip_type))
    for oa_name, oa_type in workflow.signature.outputs.items():
        parameters.append(_build_output_option(oa_name, oa_type))

    callback = _build_visualization_callback(workflow)
    return click.Command(name, params=parameters, callback=callback)


# cli entry point
def main():
    cli()
