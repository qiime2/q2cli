# ----------------------------------------------------------------------------
# Copyright (c) 2016--, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------

import click
import qiime
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
                    workflows = plugin.workflows.keys()
                    return sorted(workflows)

                def get_command(self, ctx, name):
                    workflow = plugin.workflows[name]
                    return _build_command(name, workflow)

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

# TODO: update keys to be the types (rather than their str representations)
# pending biocore/qiime2#46
#_type_map = {int: click.INT, str: click.STRING, float: click.FLOAT}


def _create_callback(wf):
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
        future_ = executor(wf,
                           inputs,
                           parameters,
                           outputs)

        # block (i.e., wait) until result is ready
        completed_process = future_.result()

        if completed_process.returncode != 0:
            click.echo(completed_process.stdout)
            click.echo(completed_process.stderr, err=True)
            ctx.exit(completed_process.returncode)

    return click.pass_context(f)


def _build_command(workflow_name, workflow):
    parameters = []
    for ia_name, ia_type in workflow.signature.inputs.items():
        p = click.Option(['--%s' % ia_name],
                         required=True,
                         type=click.Path(exists=True, dir_okay=False),
                         help='Input %s' % str(ia_type[0]))
        parameters.append(p)
    for ip_name, ip_type in workflow.signature.parameters.items():
        p = click.Option(['--%s' % ip_name],
                         required=True,
                         type=ip_type[1])
        parameters.append(p)
    for oa_name, oa_type in workflow.signature.outputs.items():
        p = click.Option(['--%s' % oa_name],
                         required=True,
                         type=click.Path(exists=False, dir_okay=False),
                         help='Output %s' % str(oa_type[0]))
        parameters.append(p)

    callback = _create_callback(workflow)
    return click.Command(workflow_name, params=parameters, callback=callback)


# cli entry point
def main():
    cli()
