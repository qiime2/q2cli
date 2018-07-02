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
               short_help='Export data from a QIIME 2 Artifact '
               'or a Visualization',
               help='Exporting extracts (and optionally transforms) data '
               'stored inside an Artifact or Visualization. Note that '
               'Visualizations cannot be transformed with --output-format'
               )
@q2cli.option('--input-path', required=True,
              type=click.Path(exists=True, file_okay=True,
                              dir_okay=False, readable=True),
              help='Path to file that should be exported')
@q2cli.option('--output-path', required=True,
              type=click.Path(exists=False, file_okay=True, dir_okay=True,
                              writable=True),
              help='Path to file or directory where '
              'data should be exported to')
@q2cli.option('--output-format', required=False,
              help='Format which the data should be exported as. '
              'This option cannot be used with Visualizations')
def export_data(input_path, output_path, output_format):
    import qiime2.sdk
    import distutils
    result = qiime2.sdk.Result.load(input_path)
    if output_format is None:
        if isinstance(result, qiime2.sdk.Artifact):
            output_format = result.format.__name__
        else:
            output_format = 'Visualization'
        result.export_data(output_path)
    else:
        if isinstance(result, qiime2.sdk.Visualization):
            error = '--output-format cannot be used with visualizations'
            click.secho(error, fg='red', bold=True, err=True)
            click.get_current_context().exit(1)
        else:
            source = result.view(qiime2.sdk.parse_format(output_format))
            if os.path.isfile(str(source)):
                os.renames(str(source), output_path)
            else:
                distutils.dir_util.copy_tree(str(source), output_path)

    output_type = 'file' if os.path.isfile(output_path) else 'directory'
    success = 'Exported %s as %s to %s %s' % (input_path, output_format,
                                              output_type, output_path)
    click.secho(success, fg='green')


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
@q2cli.option('--input-format', required=False,
              help='The format of the data to be imported. If not provided, '
                   'data must be in the format expected by the semantic type '
                   'provided via --type.')
@q2cli.option('--show-importable-types', is_flag=True, is_eager=True,
              callback=show_importable_types, expose_value=False,
              help='Show the semantic types that can be supplied to --type '
                   'to import data into an artifact.')
@q2cli.option('--show-importable-formats', is_flag=True, is_eager=True,
              callback=show_importable_formats, expose_value=False,
              help='Show formats that can be supplied to --input-format to '
                   'import data into an artifact.')
def import_data(type, input_path, output_path, input_format):
    import qiime2.sdk
    import qiime2.plugin
    try:
        artifact = qiime2.sdk.Artifact.import_data(type, input_path,
                                                   view_type=input_format)
    except qiime2.plugin.ValidationError as e:
        header = 'There was a problem importing %s:' % input_path
        q2cli.util.exit_with_error(e, header=header, traceback=None)
    except Exception as e:
        header = 'An unexpected error has occurred:'
        q2cli.util.exit_with_error(e, header=header)
    artifact.save(output_path)
    if input_format is None:
        input_format = artifact.format.__name__

    success = 'Imported %s as %s to %s' % (input_path,
                                           input_format,
                                           output_path)
    click.secho(success, fg='green')


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


@tools.command('inspect-metadata',
               short_help='Inspect columns available in metadata.',
               help='Inspect metadata files or artifacts viewable as metadata.'
                    ' Providing multiple file paths to this command will merge'
                    ' the metadata.')
@q2cli.option('--tsv/--no-tsv', default=False,
              help='Print as machine-readable TSV instead of text.')
@click.argument('paths', nargs=-1, required=True,
                type=click.Path(exists=True, file_okay=True, dir_okay=False,
                                readable=True))
@q2cli.util.pretty_failure(traceback=None)
def inspect_metadata(paths, tsv, failure):
    m = [_load_metadata(p) for p in paths]
    metadata = m[0]
    if m[1:]:
        metadata = metadata.merge(*m[1:])

    # we aren't expecting errors below this point, so set traceback to default
    failure.traceback = 'stderr'
    failure.header = "An unexpected error has occurred:"

    COLUMN_NAME = "COLUMN NAME"
    COLUMN_TYPE = "TYPE"
    max_name_len = max([len(n) for n in metadata.columns]
                       + [len(COLUMN_NAME)])
    max_type_len = max([len(p.type) for p in metadata.columns.values()]
                       + [len(COLUMN_TYPE)])

    if tsv:
        import csv
        import io

        def formatter(*row):
            # This is gross, but less gross than robust TSV writing.
            with io.StringIO() as fh:
                writer = csv.writer(fh, dialect='excel-tab', lineterminator='')
                writer.writerow(row)
                return fh.getvalue()
    else:
        formatter = ("{0:>%d}  {1:%d}" % (max_name_len, max_type_len)).format

    click.secho(formatter(COLUMN_NAME, COLUMN_TYPE), bold=True)
    if not tsv:
        click.secho(formatter("=" * max_name_len, "=" * max_type_len),
                    bold=True)

    for name, props in metadata.columns.items():
        click.echo(formatter(name, props.type))

    if not tsv:
        click.secho(formatter("=" * max_name_len, "=" * max_type_len),
                    bold=True)
        click.secho(("{0:>%d}  " % max_name_len).format("IDS:"),
                    bold=True, nl=False)
        click.echo(metadata.id_count)
        click.secho(("{0:>%d}  " % max_name_len).format("COLUMNS:"),
                    bold=True, nl=False)
        click.echo(metadata.column_count)


def _load_metadata(path):
    import qiime2
    import qiime2.sdk

    # TODO: clean up duplication between this and the metadata handlers.
    try:
        artifact = qiime2.sdk.Result.load(path)
    except Exception:
        metadata = qiime2.Metadata.load(path)
    else:
        if isinstance(artifact, qiime2.Visualization):
            raise Exception("Visualizations cannot be viewed as QIIME 2"
                            " metadata:\n%r" % path)
        elif artifact.has_metadata():
            metadata = artifact.view(qiime2.Metadata)
        else:
            raise Exception("Artifacts with type %r cannot be viewed as"
                            " QIIME 2 metadata:\n%r" % (artifact.type, path))

    return metadata


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
@q2cli.option('--input-path', required=True,
              type=click.Path(exists=True, file_okay=True, dir_okay=False,
                              readable=True),
              help='Path to file that should be extracted')
@q2cli.option('--output-path', required=False,
              type=click.Path(exists=False, file_okay=False, dir_okay=True,
                              writable=True),
              help='Directory where archive should be extracted to '
                   '[default: current working directory]',
              default=os.getcwd())
def extract(input_path, output_path):
    import zipfile
    import qiime2.sdk

    try:
        extracted_dir = qiime2.sdk.Result.extract(input_path, output_path)
    except (zipfile.BadZipFile, ValueError):
        raise click.BadParameter(
            '%s is not a valid QIIME 2 Result. Only QIIME 2 Artifacts and '
            'Visualizations can be extracted.' % input_path)
    else:
        success = 'Extracted %s to directory %s' % (input_path, extracted_dir)
        click.secho(success, fg='green')


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
        q2cli.util.exit_with_error(e, header=header, traceback=None)
    except Exception as e:
        header = ('An unexpected error has occurred while attempting to '
                  'validate artifact %s:' % path)
        q2cli.util.exit_with_error(e, header=header)
    else:
        click.secho('Artifact %s appears to be valid at level=%s.'
                    % (path, level), fg="green")


@tools.command(short_help='Print citations for a QIIME 2 result.',
               help='Print citations as a BibTex file (.bib) for a QIIME 2'
                    ' result.')
@click.argument('path', type=click.Path(exists=True, file_okay=True,
                                        dir_okay=False, readable=True))
def citations(path):
    import qiime2.sdk
    import io
    ctx = click.get_current_context()

    try:
        result = qiime2.sdk.Result.load(path)
    except Exception as e:
        header = 'There was a problem loading %s as a QIIME 2 result:' % path
        q2cli.util.exit_with_error(e, header=header)

    if result.citations:
        with io.StringIO() as fh:
            result.citations.save(fh)
            click.echo(fh.getvalue(), nl=False)
        ctx.exit(0)
    else:
        click.secho('No citations found.', fg='yellow', err=True)
        ctx.exit(1)
