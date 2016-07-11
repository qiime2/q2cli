# ----------------------------------------------------------------------------
# Copyright (c) 2016--, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------

import os
import zipfile

import click
import qiime


@click.group(help='Tools for working with QIIME files.')
def tools():
    pass


@tools.command(short_help='View a QIIME Visualization.',
               help="Displays a QIIME Visualization until the command exits. "
                    "To open a QIIME Visualization so it can be used after "
                    "the command exits, use 'qiime extract'.")
@click.argument('visualization-path')
@click.option('--index-extension', required=False, default='html',
              help='The extension of the index file that should be opened. '
                   '[default: html]')
def view(visualization_path, index_extension):
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
            # Entering either ^C or Return will cause output_dir to be
            # cleaned up.
            click.prompt('Press the Return key or ^C to quit (your '
                         'visualization may no longer be accessible)',
                         default='q', prompt_suffix='. ',
                         show_default=False)


@tools.command(help='Extract a QIIME Arifact or Visualization.')
@click.argument('path')
@click.option('--output-dir', required=False,
              type=click.Path(exists=True, dir_okay=True),
              help='Directory where result should be extracted '
                   '[default: current working directory]',
              default=os.getcwd())
def extract(path, output_dir):
    try:
        qiime.sdk.Result.extract(path, output_dir)
    except zipfile.BadZipFile:
        raise click.BadParameter(
            '%s is not a QIIME Result. Only QIIME Visualizations and Artifacts'
            ' can be extracted.' % path)
