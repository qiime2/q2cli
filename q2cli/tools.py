# ----------------------------------------------------------------------------
# Copyright (c) 2016-2018, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import os

import click

import q2cli


@click.group(help='Tools for working with QIIME 2 files.')
def tools():
    pass


@tools.command(name='export',
               short_help='Export data from a QIIME 2 Artifact or '
                          'Visualization.',
               help="Export data from a QIIME 2 Artifact or Visualization. "
                    "Exporting extracts the data stored in an Artifact or "
                    "Visualization and will support exporting to multiple "
                    "formats in the future. For now, the data is exported in "
                    "the format it is stored within the Artifact or "
                    "Visualization. Use 'qiime tools extract' to extract the "
                    "Artifact or Visualization's entire archive.")
@click.argument('path', type=click.Path(exists=True, file_okay=True,
                                        dir_okay=False, readable=True))
@q2cli.option('--output-dir', required=True,
              type=click.Path(exists=False, file_okay=False, dir_okay=True,
                              writable=True),
              help='Directory where data should be exported to')
def export_data(path, output_dir):
    import qiime2.sdk

    result = qiime2.sdk.Result.load(path)
    result.export_data(output_dir)


def show_importable_types(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return

    import qiime2.sdk

    importable_types = sorted(qiime2.sdk.PluginManager().importable_types,
                              key=repr)

    if importable_types:
        for name in importable_types:
            click.echo(name)
    else:
        click.echo('There are no importable types in the current deployment.')

    ctx.exit()


def show_importable_formats(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return

    import qiime2.sdk

    importable_formats = sorted(qiime2.sdk.PluginManager().importable_formats)

    if importable_formats:
        for format in importable_formats:
            click.echo(format)
    else:
        click.echo('There are no importable formats '
                   'in the current deployment.')

    ctx.exit()


@tools.command(name='import',
               short_help='Import data into a new QIIME 2 Artifact.',
               help="Import data to create a new QIIME 2 Artifact. See "
                    "https://docs.qiime2.org/ for usage examples and details "
                    "on the file types and associated semantic types that can "
                    "be imported.")
@q2cli.option('--type', required=True,
              help='The semantic type of the artifact that will be created '
                   'upon importing. Use --show-importable-types to see what '
                   'importable semantic types are available in the current '
                   'deployment.')
@q2cli.option('--input-path', required=True,
              type=click.Path(exists=True, file_okay=True, dir_okay=True,
                              readable=True),
              help='Path to file or directory that should be imported.')
@q2cli.option('--output-path', required=True,
              type=click.Path(exists=False, file_okay=True, dir_okay=False,
                              writable=True),
              help='Path where output artifact should be written.')
@q2cli.option('--source-format', required=False,
              help='The format of the data to be imported. If not provided, '
                   'data must be in the format expected by the semantic type '
                   'provided via --type.')
@q2cli.option('--show-importable-types', is_flag=True, is_eager=True,
              callback=show_importable_types, expose_value=False,
              help='Show the semantic types that can be supplied to --type '
                   'to import data into an artifact.')
@q2cli.option('--show-importable-formats', is_flag=True, is_eager=True,
              callback=show_importable_formats, expose_value=False,
              help='Show formats that can be supplied to --source-format to '
                   'import data into an artifact.')
def import_data(type, input_path, output_path, source_format):
    import qiime2.sdk
    import qiime2.plugin
    try:
        artifact = qiime2.sdk.Artifact.import_data(type, input_path,
                                                   view_type=source_format)
    except qiime2.plugin.ValidationError as e:
        header = 'There was a problem importing %s:' % input_path
        with open(os.devnull, 'w') as dev_null:
            q2cli.util.exit_with_error(e, header=header, file=dev_null,
                                       suppress_footer=True)
    except Exception as e:
        header = 'An unexpected error has occurred:'
        q2cli.util.exit_with_error(e, header=header)
    artifact.save(output_path)


@tools.command(short_help='Take a peek at a QIIME 2 Artifact or '
                          'Visualization.',
               help="Display basic information about a QIIME 2 Artifact or "
                    "Visualization, including its UUID and type.")
@click.argument('path', type=click.Path(exists=True, file_okay=True,
                                        dir_okay=False, readable=True))
def peek(path):
    import qiime2.sdk

    metadata = qiime2.sdk.Result.peek(path)

    click.secho("UUID:        ", fg="green", nl=False)
    click.secho(metadata.uuid)
    click.secho("Type:        ", fg="green", nl=False)
    click.secho(metadata.type)
    if metadata.format is not None:
        click.secho("Data format: ", fg="green", nl=False)
        click.secho(metadata.format)


@tools.command(short_help='View a QIIME 2 Visualization.',
               help="Displays a QIIME 2 Visualization until the command "
                    "exits. To open a QIIME 2 Visualization so it can be "
                    "used after the command exits, use 'qiime extract'.")
@click.argument('visualization-path',
                type=click.Path(exists=True, file_okay=True, dir_okay=False,
                                readable=True))
@q2cli.option('--index-extension', required=False, default='html',
              help='The extension of the index file that should be opened. '
                   '[default: html]')
def view(visualization_path, index_extension):
    # Guard headless envs from having to import anything large
    import sys
    if not os.getenv("DISPLAY") and sys.platform != "darwin":
        raise click.UsageError(
            'Visualization viewing is currently not supported in headless '
            'environments. You can view Visualizations (and Artifacts) at '
            'https://view.qiime2.org, or move the Visualization to an '
            'environment with a display and view it with `qiime tools view`.')

    import zipfile
    import qiime2.sdk

    if index_extension.startswith('.'):
        index_extension = index_extension[1:]
    try:
        visualization = qiime2.sdk.Visualization.load(visualization_path)
    # TODO: currently a KeyError is raised if a zipped file that is not a
    # QIIME 2 result is passed. This should be handled better by the framework.
    except (zipfile.BadZipFile, KeyError, TypeError):
        raise click.BadParameter(
            '%s is not a QIIME 2 Visualization. Only QIIME 2 Visualizations '
            'can be viewed.' % visualization_path)

    index_paths = visualization.get_index_paths(relative=False)

    if index_extension not in index_paths:
        raise click.BadParameter(
            'No index %s file with is present in the archive. Available index '
            'extensions are: %s' % (index_extension,
                                    ', '.join(index_paths.keys())))
    else:
        index_path = index_paths[index_extension]
        launch_status = click.launch(index_path)
        if launch_status != 0:
            click.echo('Viewing visualization failed while attempting to '
                       'open %s' % index_path, err=True)
        else:
            while True:
                click.echo(
                    "Press the 'q' key, Control-C, or Control-D to quit. This "
                    "view may no longer be accessible or work correctly after "
                    "quitting.", nl=False)
                # There is currently a bug in click.getchar where translation
                # of Control-C and Control-D into KeyboardInterrupt and
                # EOFError (respectively) does not work on Python 3. The code
                # here should continue to work as expected when the bug is
                # fixed in Click.
                #
                # https://github.com/pallets/click/issues/583
                try:
                    char = click.getchar()
                    click.echo()
                    if char in {'q', '\x03', '\x04'}:
                        break
                except (KeyboardInterrupt, EOFError):
                    break


@tools.command(short_help="Extract a QIIME 2 Artifact or Visualization "
                          "archive.",
               help="Extract all contents of a QIIME 2 Artifact or "
                    "Visualization's archive, including provenance, metadata, "
                    "and actual data. Use 'qiime tools export' to export only "
                    "the data stored in an Artifact or Visualization, with "
                    "the choice of exporting to different formats.")
@click.argument('path', type=click.Path(exists=True, file_okay=True,
                                        dir_okay=False, readable=True))
@q2cli.option('--output-dir', required=False,
              type=click.Path(exists=True, file_okay=False, dir_okay=True,
                              writable=True),
              help='Directory where archive should be extracted to '
                   '[default: current working directory]',
              default=os.getcwd())
def extract(path, output_dir):
    import zipfile
    import qiime2.sdk

    try:
        extracted_dir = qiime2.sdk.Result.extract(path, output_dir)
    except (zipfile.BadZipFile, ValueError):
        raise click.BadParameter(
            '%s is not a valid QIIME 2 Result. Only QIIME 2 Artifacts and '
            'Visualizations can be extracted.' % path)
    else:
        click.echo('Extracted to %s' % extracted_dir)


@tools.command(short_help='Validate data in a QIIME 2 Artifact.',
               help='Validate data in a QIIME 2 Artifact. QIIME 2 '
                    'automatically performs some basic validation when '
                    'managing your data; use this command to perform explicit '
                    'and/or more thorough validation of your data (e.g. when '
                    'debugging issues with your data or analyses).\n\nNote: '
                    'validation can take some time to complete, depending on '
                    'the size and type of your data.')
@click.argument('path', type=click.Path(exists=True, file_okay=True,
                                        dir_okay=False, readable=True))
@q2cli.option('--level', required=False, type=click.Choice(['min', 'max']),
              help='Desired level of validation. "min" will perform minimal '
                   'validation, and "max" will perform maximal validation (at '
                   'the potential cost of runtime).',
              default='max', show_default=True)
def validate(path, level):
    import qiime2.sdk

    try:
        artifact = qiime2.sdk.Artifact.load(path)
    except Exception as e:
        header = 'There was a problem loading %s as a QIIME 2 Artifact:' % path
        q2cli.util.exit_with_error(e, header=header)

    try:
        artifact.validate(level)
    except qiime2.plugin.ValidationError as e:
        header = 'Artifact %s does not appear to be valid at level=%s:' % (
                path, level)
        with open(os.devnull, 'w') as dev_null:
            q2cli.util.exit_with_error(e, header=header, file=dev_null,
                                       suppress_footer=True)
    except Exception as e:
        header = ('An unexpected error has occurred while attempting to '
                  'validate artifact %s:' % path)
        q2cli.util.exit_with_error(e, header=header)
    else:
        click.secho('Artifact %s appears to be valid at level=%s.'
                    % (path, level), fg="green")
