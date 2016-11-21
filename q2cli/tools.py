# ----------------------------------------------------------------------------
# Copyright (c) 2016--, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------

import os

import click


@click.group(help='Tools for working with QIIME files.')
def tools():
    pass


@tools.command(name='export',
               short_help='Export data from a QIIME Artifact or '
                          'Visualization.',
               help="Export data from a QIIME Artifact or Visualization. "
                    "Exporting extracts the data stored in an Artifact or "
                    "Visualization and will support exporting to multiple "
                    "formats in the future. For now, the data is exported in "
                    "the format it is stored within the Artifact or "
                    "Visualization. Use 'qiime tools extract' to extract the "
                    "Artifact or Visualization's entire archive.")
@click.argument('path', type=click.Path(exists=True, dir_okay=False))
@click.option('--output-dir', required=True,
              type=click.Path(exists=False, dir_okay=True),
              help='Directory where data should be exported to')
def export_data(path, output_dir):
    import qiime.sdk

    result = qiime.sdk.Result.load(path)
    result.export_data(output_dir)


@tools.command(name='import',
               short_help='Import data into a new QIIME Artifact.',
               help="Import data to create a new QIIME Artifact. See "
                    "https://docs.qiime2.org/ for usage examples and details "
                    "on the file types and associated semantic types that can "
                    "be imported.")
@click.option('--type', required=True,
              help='The semantic type of the new artifact.')
@click.option('--input-path', required=True,
              type=click.Path(exists=True, dir_okay=True),
              help='Path to file or directory that should be imported.')
@click.option('--output-path', required=True,
              type=click.Path(exists=False, dir_okay=False),
              help='Path where output artifact should be written.')
@click.option('--source-format', required=False,
              help='The format of the data to be imported. If not provided, '
                   'data must be in the format expected by the semantic type '
                   'provided via --type.')
def import_data(type, input_path, output_path, source_format=None):
    import qiime.sdk

    artifact = qiime.sdk.Artifact.import_data(type, input_path,
                                              view_type=source_format)
    artifact.save(output_path)


@tools.command(short_help='Take a peek at a QIIME Artifact or Visualization.',
               help="Display basic information about a QIIME Artifact or "
                    "Visualization, including its UUID and type.")
@click.argument('path', type=click.Path(exists=True, dir_okay=False))
def peek(path):
    import qiime.sdk

    metadata = qiime.sdk.Result.peek(path)

    click.secho("UUID:        ", fg="green", nl=False)
    click.secho(metadata.uuid)
    click.secho("Type:        ", fg="green", nl=False)
    click.secho(metadata.type)
    if metadata.format is not None:
        click.secho("Data format: ", fg="green", nl=False)
        click.secho(metadata.format)


@tools.command(short_help='View a QIIME Visualization.',
               help="Displays a QIIME Visualization until the command exits. "
                    "To open a QIIME Visualization so it can be used after "
                    "the command exits, use 'qiime extract'.")
@click.argument('visualization-path',
                type=click.Path(exists=True, dir_okay=False))
@click.option('--index-extension', required=False, default='html',
              help='The extension of the index file that should be opened. '
                   '[default: html]')
def view(visualization_path, index_extension):
    # Guard headless envs from having to import anything
    if not os.getenv("DISPLAY"):
        raise click.UsageError(
            'Visualization viewing is currently not supported in headless '
            'environments. You can view Visualizations (and Artifacts) at '
            'https://view.qiime2.org, or move the Visualization to an '
            'environment with a display and view it with `qiime tools view`.')

    import zipfile
    import qiime.sdk

    if index_extension.startswith('.'):
        index_extension = index_extension[1:]
    try:
        visualization = qiime.sdk.Visualization.load(visualization_path)
    # TODO: currently a KeyError is raised if a zipped file that is not a
    # QIIME result is passed. This should be handled better by the framework.
    except (zipfile.BadZipFile, KeyError, TypeError):
        raise click.BadParameter(
            '%s is not a QIIME Visualization. Only QIIME Visualizations can '
            'be viewed.' % visualization_path)

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


@tools.command(short_help="Extract a QIIME Artifact or Visualization archive.",
               help="Extract all contents of a QIIME Artifact or "
                    "Visualization's archive, including provenance, metadata, "
                    "and actual data. Use 'qiime tools export' to export only "
                    "the data stored in an Artifact or Visualization, with "
                    "the choice of exporting to different formats.")
@click.argument('path', type=click.Path(exists=True, dir_okay=False))
@click.option('--output-dir', required=False,
              type=click.Path(exists=True, dir_okay=True),
              help='Directory where archive should be extracted to '
                   '[default: current working directory]',
              default=os.getcwd())
def extract(path, output_dir):
    import zipfile
    import qiime.sdk

    try:
        extracted_dir = qiime.sdk.Result.extract(path, output_dir)
    except (zipfile.BadZipFile, ValueError):
        raise click.BadParameter(
            '%s is not a valid QIIME Result. Only QIIME Artifacts and '
            'Visualizations can be extracted.' % path)
    else:
        click.echo('Extracted to %s' % extracted_dir)
