# ----------------------------------------------------------------------------
# Copyright (c) 2016-2023, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import os

import click

import q2cli.util
from q2cli.click.command import ToolCommand, ToolGroupCommand

_COMBO_METAVAR = 'ARTIFACT/VISUALIZATION'


@click.group(help='Tools for working with QIIME 2 files.',
             cls=ToolGroupCommand)
def tools():
    pass


@tools.command(name='export',
               short_help='Export data from a QIIME 2 Artifact '
               'or a Visualization',
               help='Exporting extracts (and optionally transforms) data '
               'stored inside an Artifact or Visualization. Note that '
               'Visualizations cannot be transformed with --output-format',
               cls=ToolCommand)
@click.option('--input-path', required=True, metavar=_COMBO_METAVAR,
              type=click.Path(exists=True, file_okay=True,
                              dir_okay=False, readable=True),
              help='Path to file that should be exported')
@click.option('--output-path', required=True,
              type=click.Path(exists=False, file_okay=True, dir_okay=True,
                              writable=True),
              help='Path to file or directory where '
              'data should be exported to')
@click.option('--output-format', required=False,
              help='Format which the data should be exported as. '
              'This option cannot be used with Visualizations')
def export_data(input_path, output_path, output_format):
    import qiime2.util
    import qiime2.sdk
    import distutils
    from q2cli.core.config import CONFIG
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
            click.echo(CONFIG.cfg_style('error', error), err=True)
            click.get_current_context().exit(1)
        else:
            source = result.view(qiime2.sdk.parse_format(output_format))
            if os.path.isfile(str(source)):
                if os.path.isfile(output_path):
                    os.remove(output_path)
                elif os.path.dirname(output_path) == '':
                    # This allows the user to pass a filename as a path if they
                    # want their output in the current working directory
                    output_path = os.path.join('.', output_path)
                if os.path.dirname(output_path) != '':
                    # create directory (recursively) if it doesn't exist yet
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                qiime2.util.duplicate(str(source), output_path)
            else:
                distutils.dir_util.copy_tree(str(source), output_path)

    output_type = 'file' if os.path.isfile(output_path) else 'directory'
    success = 'Exported %s as %s to %s %s' % (input_path, output_format,
                                              output_type, output_path)
    click.echo(CONFIG.cfg_style('success', success))



def print_descriptions(descriptions, tsv):
    if tsv:
        for value, description in descriptions.items():
            click.echo(f"{value}\t", nl=False)
            if description:
                click.echo(description)
            else:
                click.echo()
    else:
        import textwrap
        for value, description in descriptions.items():
            click.secho(value, bold=True)
            if description:
                tabsize = 8
                wrapped_description = textwrap.wrap(description, 
                                                    width=72-tabsize, 
                                                    initial_indent='\t', 
                                                    subsequent_indent='\t',
                                                    tabsize=tabsize)
                for line in wrapped_description:
                    click.echo(f"{line}")
            else:
                click.secho("\tNo description", italic=True)
            click.echo()

def get_matches(words, possibilities, cutoff=0.5):
    from difflib import get_close_matches
    matches = []
    for word in words:
        matches += get_close_matches(word, 
                                    possibilities, 
                                    n=len(possibilities),
                                    cutoff=cutoff) 
        # simple substring search 
        for possibility in possibilities:
            if word.lower() in possibility.lower() \
                and possibility not in matches:
                matches.append(possibility)

    return matches 


@tools.command(
        name='show-types',
        help='List the available semantic types.',
        short_help='',
        cls=ToolCommand
)
@click.argument('types', nargs=-1)
@click.option('--strict', is_flag=True,
              help='Show only exact matches for the type argument(s).')
@click.option('--tsv', is_flag=True,
              help='Print as machine readable tab separated values.')
def show_types(types, strict, tsv):
    pm = q2cli.util.get_plugin_manager()

    if types and strict:
        matches = get_matches(types, list(pm.artifact_classes), 1)
    elif types:
        matches = get_matches(types, list(pm.artifact_classes))
    else:
        matches = list(pm.artifact_classes)

    descriptions = {}
    for match in sorted(matches):
        description = pm.artifact_classes[match].description
        descriptions[match] = description

    print_descriptions(descriptions, tsv)

@tools.command(
        name='show-formats',
        help='List the availabe formats.',
        short_help='',
        cls=ToolCommand
)
@click.argument('formats', nargs=-1)
@click.option('--importable', is_flag=True, 
              help='List the importable formats.')
@click.option('--exportable', is_flag=True, 
              help='List the exportable formats.')
@click.option('--strict', is_flag=True,
              help='Show only exact matches for the format argument(s).')
@click.option('--tsv', is_flag=True,
              help='Print as machine readable tab separated values.')
def show_formats(formats, importable, exportable, strict, tsv):
    if importable and exportable:
        raise click.UsageError("'--importable' and '--exportable' flags are "
                               "mutually exclusive.")
    if not importable and not exportable:
        raise click.UsageError("One of '--importable' or '--exportable' flags "
                               "is required.")

    pm = q2cli.util.get_plugin_manager()
    available_formats = list(pm.importable_formats) if importable \
                        else list(pm.exportable_formats)

    if formats and strict:
        matches = get_matches(formats, available_formats, 1)
    elif formats:
        matches = get_matches(formats, available_formats)
    else:
        matches = available_formats    

    descriptions = {}
    for match in sorted(matches):
        docstring = pm.importable_formats[match].format.__doc__ 
        first_docstring_line = docstring.split('\n\n')[0].strip() \
                               if docstring else ''
        descriptions[match] = first_docstring_line

    print_descriptions(descriptions, tsv)



def show_importable_types(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return

    import q2cli.util

    importable_types = sorted(q2cli.util.get_plugin_manager().importable_types,
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

    import q2cli.util

    importable_formats = sorted(
            q2cli.util.get_plugin_manager().importable_formats)

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
                    "be imported.",
                    cls=ToolCommand)
@click.option('--type', required=True,
              help='The semantic type of the artifact that will be created '
                   'upon importing. Use --show-importable-types to see what '
                   'importable semantic types are available in the current '
                   'deployment.')
@click.option('--input-path', required=True,
              type=click.Path(exists=True, file_okay=True, dir_okay=True,
                              readable=True),
              help='Path to file or directory that should be imported.')
@click.option('--output-path', required=True, metavar='ARTIFACT',
              type=click.Path(exists=False, file_okay=True, dir_okay=False,
                              writable=True),
              help='Path where output artifact should be written.')
@click.option('--input-format', required=False,
              help='The format of the data to be imported. If not provided, '
                   'data must be in the format expected by the semantic type '
                   'provided via --type.')
@click.option('--show-importable-types', is_flag=True, is_eager=True,
              callback=show_importable_types, expose_value=False,
              help='Show the semantic types that can be supplied to --type '
                   'to import data into an artifact.')
@click.option('--show-importable-formats', is_flag=True, is_eager=True,
              callback=show_importable_formats, expose_value=False,
              help='Show formats that can be supplied to --input-format to '
                   'import data into an artifact.')
def import_data(type, input_path, output_path, input_format):
    import qiime2.sdk
    import qiime2.plugin
    from q2cli.core.config import CONFIG
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
    click.echo(CONFIG.cfg_style('success', success))


@tools.command(short_help='Take a peek at a QIIME 2 Artifact or '
                          'Visualization.',
               help="Display basic information about a QIIME 2 Artifact or "
                    "Visualization, including its UUID and type.",
               cls=ToolCommand)
@click.argument('paths', nargs=-1, required=True,
                type=click.Path(exists=True, file_okay=True, dir_okay=False,
                                readable=True), metavar=_COMBO_METAVAR)
@click.option('--tsv/--no-tsv', default=False,
              help='Print as machine-readable tab separated values.')
def peek(paths, tsv):
    import qiime2.sdk
    from q2cli.core.config import CONFIG

    metadatas = {os.path.basename(path):
                 qiime2.sdk.Result.peek(path) for path in paths}

    if tsv:
        click.echo("Filename\tType\tUUID\tData Format")
        for path, m in metadatas.items():
            click.echo(f"{path}\t{m.type}\t{m.uuid}\t{m.format}")

    elif len(metadatas) == 1:
        metadata = metadatas[os.path.basename(paths[0])]
        click.echo(CONFIG.cfg_style('type', "UUID")+":        ", nl=False)
        click.echo(metadata.uuid)
        click.echo(CONFIG.cfg_style('type', "Type")+":        ", nl=False)
        click.echo(metadata.type)
        if metadata.format is not None:
            click.echo(CONFIG.cfg_style('type', "Data format")+": ", nl=False)
            click.echo(metadata.format)

    else:
        COLUMN_FILENAME = "Filename"
        COLUMN_TYPE = "Type"
        COLUMN_UUID = "UUID"
        COLUMN_DATA_FORMAT = "Data Format"

        filename_width = max([len(p) for p in paths]
                             + [len(COLUMN_FILENAME)])
        type_width = max([len(i.type) for i in metadatas.values()]
                         + [len(COLUMN_TYPE)])
        uuid_width = max([len(i.uuid) for i in metadatas.values()]
                         + [len(COLUMN_UUID)])
        data_format_width = \
            max([len(i.format) if i.format is not None else 0
                 for i in metadatas.values()] + [len(COLUMN_DATA_FORMAT)])

        padding = 2
        format_string = f"{{f:<{filename_width + padding}}} " + \
                        f"{{t:<{type_width + padding}}} " + \
                        f"{{u:<{uuid_width + padding}}} " + \
                        f"{{d:<{data_format_width + padding}}}"

        click.secho(
            format_string.format(
                f=COLUMN_FILENAME,
                t=COLUMN_TYPE,
                u=COLUMN_UUID,
                d=COLUMN_DATA_FORMAT),
            bold=True, fg="green")
        for path, m in metadatas.items():
            click.echo(
                format_string.format(
                    f=path,
                    t=m.type,
                    u=m.uuid,
                    d=(m.format if m.format is not None else 'N/A')))


_COLUMN_TYPES = ['categorical', 'numeric']


@tools.command(name='cast-metadata',
               short_help='Designate metadata column types.',
               help='Designate metadata column types.'
                    ' Supported column types are as follows: %s.'
                    ' Providing multiple file paths to this command will merge'
                    ' the metadata.' % (', '.join(_COLUMN_TYPES)),
               cls=ToolCommand)
@click.option('--cast', required=True, metavar='COLUMN:TYPE', multiple=True,
              help='Parameter for each metadata column that should'
              ' be cast as a specified column type (supported types are as'
              ' follows: %s). The required formatting for this'
              ' parameter is --cast COLUMN:TYPE, repeated for each column'
              ' and the associated column type it should be cast to in'
              ' the output.' % (', '.join(_COLUMN_TYPES)))
@click.option('--ignore-extra', is_flag=True,
              help='If this flag is enabled, cast parameters that do not'
              ' correspond to any of the column names within the provided'
              ' metadata will be ignored.')
@click.option('--error-on-missing', is_flag=True,
              help='If this flag is enabled, failing to include cast'
              ' parameters for all columns in the provided metadata will'
              ' result in an error.')
@click.option('--output-file', required=False,
              type=click.Path(exists=False, file_okay=True, dir_okay=False,
                              writable=True),
              help='Path to file where the modified metadata should be'
              ' written to.')
@click.argument('paths', nargs=-1, required=True, metavar='METADATA...',
                type=click.Path(exists=True, file_okay=True, dir_okay=False,
                                readable=True))
def cast_metadata(paths, cast, output_file, ignore_extra,
                  error_on_missing):
    import tempfile
    from qiime2 import Metadata, metadata

    md = _merge_metadata(paths)

    cast_dict = {}
    try:
        for casting in cast:
            if ':' not in casting:
                raise click.BadParameter(
                    message=f'Missing `:` in --cast {casting}',
                    param_hint='cast')
            splitter = casting.split(':')
            if len(splitter) != 2:
                raise click.BadParameter(
                    message=f'Incorrect number of fields in --cast {casting}.'
                            f' Observed {len(splitter)}'
                            f' {tuple(splitter)}, expected 2.',
                    param_hint='cast')
            col, type_ = splitter
            if col in cast_dict:
                raise click.BadParameter(
                    message=(f'Column name "{col}" appears in cast more than'
                             ' once.'),
                    param_hint='cast')
            cast_dict[col] = type_
    except Exception as err:
        header = \
            ('Could not parse provided cast arguments into unique COLUMN:TYPE'
             ' pairs. Please make sure all cast flags are of the format --cast'
             ' COLUMN:TYPE')
        q2cli.util.exit_with_error(err, header=header)

    types = set(cast_dict.values())
    if not types.issubset(_COLUMN_TYPES):
        raise click.BadParameter(
            message=('Unknown column type provided. Please make sure all'
                     ' columns included in your cast contain a valid column'
                     ' type. Valid types: %s' %
                     (', '.join(_COLUMN_TYPES))),
            param_hint='cast')

    column_names = set(md.columns.keys())
    cast_names = set(cast_dict.keys())

    if not ignore_extra:
        if not cast_names.issubset(column_names):
            cast = cast_names.difference(column_names)
            raise click.BadParameter(
                message=('The following cast columns were not found'
                         ' within the metadata: %s' %
                         (', '.join(cast))),
                param_hint='cast')

    if error_on_missing:
        if not column_names.issubset(cast_names):
            cols = column_names.difference(cast_names)
            raise click.BadParameter(
                message='The following columns within the metadata'
                        ' were not provided in the cast: %s' %
                        (', '.join(cols)),
                param_hint='cast')

    # Remove entries from the cast dict that are not in the metadata to avoid
    # errors further down the road
    for cast in cast_names:
        if cast not in column_names:
            cast_dict.pop(cast)

    with tempfile.NamedTemporaryFile() as temp:
        md.save(temp.name)
        try:
            cast_md = Metadata.load(temp.name, cast_dict)
        except metadata.io.MetadataFileError as e:
            raise click.BadParameter(message=e, param_hint='cast') from e

    if output_file:
        cast_md.save(output_file)
    else:
        with tempfile.NamedTemporaryFile(mode='w+') as stdout_temp:
            cast_md.save(stdout_temp.name)
            stdout_str = stdout_temp.read()
            click.echo(stdout_str)


@tools.command(name='inspect-metadata',
               short_help='Inspect columns available in metadata.',
               help='Inspect metadata files or artifacts viewable as metadata.'
                    ' Providing multiple file paths to this command will merge'
                    ' the metadata.',
               cls=ToolCommand)
@click.option('--tsv/--no-tsv', default=False,
              help='Print as machine-readable TSV instead of text.')
@click.argument('paths', nargs=-1, required=True, metavar='METADATA...',
                type=click.Path(file_okay=True, dir_okay=False, readable=True))
@q2cli.util.pretty_failure(traceback=None)
def inspect_metadata(paths, tsv, failure):
    metadata = _merge_metadata(paths)

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


def _merge_metadata(paths):
    m = [q2cli.util.load_metadata(p) for p in paths]
    metadata = m[0]
    if m[1:]:
        metadata = metadata.merge(*m[1:])

    return metadata


@tools.command(short_help='View a QIIME 2 Visualization.',
               help="Displays a QIIME 2 Visualization until the command "
                    "exits. To open a QIIME 2 Visualization so it can be "
                    "used after the command exits, use 'qiime tools extract'.",
               cls=ToolCommand)
@click.argument('visualization-path', metavar='VISUALIZATION',
                type=click.Path(file_okay=True, dir_okay=False, readable=True))
@click.option('--index-extension', required=False, default='html',
              help='The extension of the index file that should be opened. '
                   '[default: html]')
def view(visualization_path, index_extension):
    # Guard headless envs from having to import anything large
    import sys
    from qiime2 import Visualization
    from q2cli.util import _load_input
    from q2cli.core.config import CONFIG
    if not os.getenv("DISPLAY") and sys.platform != "darwin":
        raise click.UsageError(
            'Visualization viewing is currently not supported in headless '
            'environments. You can view Visualizations (and Artifacts) at '
            'https://view.qiime2.org, or move the Visualization to an '
            'environment with a display and view it with `qiime tools view`.')

    if index_extension.startswith('.'):
        index_extension = index_extension[1:]

    visualization = _load_input(visualization_path, view=True)[0]
    if not isinstance(visualization, Visualization):
        raise click.BadParameter(
            '%s is not a QIIME 2 Visualization. Only QIIME 2 Visualizations '
            'can be viewed.' % visualization_path)

    index_paths = visualization.get_index_paths(relative=False)

    if index_extension not in index_paths:
        raise click.BadParameter(
            'No index %s file is present in the archive. Available index '
            'extensions are: %s' % (index_extension,
                                    ', '.join(index_paths.keys())))
    else:
        index_path = index_paths[index_extension]
        launch_status = click.launch(index_path)
        if launch_status != 0:
            click.echo(CONFIG.cfg_style('error', 'Viewing visualization '
                                        'failed while attempting to open '
                                        f'{index_path}'), err=True)
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
                    "the choice of exporting to different formats.",
               cls=ToolCommand)
@click.option('--input-path', required=True, metavar=_COMBO_METAVAR,
              type=click.Path(exists=True, file_okay=True, dir_okay=False,
                              readable=True),
              help='Path to file that should be extracted')
@click.option('--output-path', required=False,
              type=click.Path(exists=False, file_okay=False, dir_okay=True,
                              writable=True),
              help='Directory where archive should be extracted to '
                   '[default: current working directory]',
              default=os.getcwd())
def extract(input_path, output_path):
    import zipfile
    import qiime2.sdk
    from q2cli.core.config import CONFIG

    try:
        extracted_dir = qiime2.sdk.Result.extract(input_path, output_path)
    except (zipfile.BadZipFile, ValueError):
        raise click.BadParameter(
            '%s is not a valid QIIME 2 Result. Only QIIME 2 Artifacts and '
            'Visualizations can be extracted.' % input_path)
    else:
        success = 'Extracted %s to directory %s' % (input_path, extracted_dir)
        click.echo(CONFIG.cfg_style('success', success))


@tools.command(short_help='Validate data in a QIIME 2 Artifact.',
               help='Validate data in a QIIME 2 Artifact. QIIME 2 '
                    'automatically performs some basic validation when '
                    'managing your data; use this command to perform explicit '
                    'and/or more thorough validation of your data (e.g. when '
                    'debugging issues with your data or analyses).\n\nNote: '
                    'validation can take some time to complete, depending on '
                    'the size and type of your data.',
               cls=ToolCommand)
@click.argument('path', type=click.Path(exists=True, file_okay=True,
                                        dir_okay=False, readable=True),
                metavar=_COMBO_METAVAR)
@click.option('--level', required=False, type=click.Choice(['min', 'max']),
              help='Desired level of validation. "min" will perform minimal '
                   'validation, and "max" will perform maximal validation (at '
                   'the potential cost of runtime).',
              default='max', show_default=True)
def validate(path, level):
    import qiime2.sdk
    from q2cli.core.config import CONFIG

    try:
        result = qiime2.sdk.Result.load(path)
    except Exception as e:
        header = 'There was a problem loading %s as a QIIME 2 Result:' % path
        q2cli.util.exit_with_error(e, header=header)

    try:
        result.validate(level)
    except qiime2.plugin.ValidationError as e:
        header = 'Result %s does not appear to be valid at level=%s:' % (
                path, level)
        q2cli.util.exit_with_error(e, header=header, traceback=None)
    except Exception as e:
        header = ('An unexpected error has occurred while attempting to '
                  'validate result %s:' % path)
        q2cli.util.exit_with_error(e, header=header)
    else:
        click.echo(CONFIG.cfg_style('success', f'Result {path} appears to be '
                                    f'valid at level={level}.'))


@tools.command(short_help='Print citations for a QIIME 2 result.',
               help='Print citations as a BibTex file (.bib) for a QIIME 2'
                    ' result.',
               cls=ToolCommand)
@click.argument('path', type=click.Path(exists=True, file_okay=True,
                                        dir_okay=False, readable=True),
                metavar=_COMBO_METAVAR)
def citations(path):
    import qiime2.sdk
    import io
    from q2cli.core.config import CONFIG
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
        click.echo(CONFIG.cfg_style('problem', 'No citations found.'),
                   err=True)
        ctx.exit(1)


@tools.command(name='cache-create',
               short_help='Create an empty cache at the given location.',
               help='Create an empty cache at the given location.',
               cls=ToolCommand)
@click.option('--cache', required=True,
              type=click.Path(exists=False, readable=True),
              help='Path to a nonexistent directory to be created as a cache.')
def cache_create(cache):
    from qiime2.core.cache import Cache
    from q2cli.core.config import CONFIG

    try:
        Cache(cache)
    except Exception as e:
        header = "There was a problem creating a cache at '%s':" % cache
        q2cli.util.exit_with_error(e, header=header, traceback=None)

    success = "Created cache at '%s'" % cache
    click.echo(CONFIG.cfg_style('success', success))


@tools.command(name='cache-remove',
               short_help='Removes a given key from a cache.',
               help='Removes a given key from a cache then runs garbage '
                    'collection on the cache.',
               cls=ToolCommand)
@click.option('--cache', required=True,
              type=click.Path(exists=True, file_okay=False, dir_okay=True,
                              readable=True),
              help='Path to an existing cache to remove the key from.')
@click.option('--key', required=True,
              help='The key to remove from the cache.')
def cache_remove(cache, key):
    from qiime2.core.cache import Cache
    from q2cli.core.config import CONFIG

    try:
        _cache = Cache(cache)
        _cache.remove(key)
    except Exception as e:
        header = "There was a problem removing the key '%s' from the " \
                 "cache '%s':" % (key, cache)
        q2cli.util.exit_with_error(e, header=header, traceback=None)

    success = "Removed key '%s' from cache '%s'" % (key, cache)
    click.echo(CONFIG.cfg_style('success', success))


@tools.command(name='cache-garbage-collection',
               short_help='Runs garbage collection on the cache at the '
                          'specified location.',
               help='Runs garbage collection on the cache at the specified '
                    'location if the specified location is a cache.',
               cls=ToolCommand)
@click.option('--cache', required=True,
              type=click.Path(exists=True, file_okay=False, dir_okay=True,
                              readable=True),
              help='Path to an existing cache to run garbage collection on.')
def cache_garbage_collection(cache):
    from qiime2.core.cache import Cache
    from q2cli.core.config import CONFIG

    try:
        _cache = Cache(cache)
        _cache.garbage_collection()
    except Exception as e:
        header = "There was a problem running garbage collection on the " \
            "cache at '%s':" % cache
        q2cli.util.exit_with_error(e, header=header, traceback=None)

    success = "Ran garbage collection on cache at '%s'" % cache
    click.echo(CONFIG.cfg_style('success', success))


@tools.command(name='cache-store',
               short_help='Stores a .qza in the cache under a key.',
               help='Stores a .qza in the cache under a key.',
               cls=ToolCommand)
@click.option('--cache', required=True,
              type=click.Path(exists=True, file_okay=False, dir_okay=True,
                              readable=True),
              help='Path to an existing cache to save into.')
@click.option('--artifact-path', required=True,
              type=click.Path(exists=True, file_okay=True, dir_okay=False,
                              readable=True),
              help='Path to a .qza to save into the cache.')
@click.option('--key', required=True,
              help='The key to save the artifact under (must be a valid '
                   'Python identifier).')
def cache_store(cache, artifact_path, key):
    from qiime2.sdk.result import Result
    from qiime2.core.cache import Cache
    from q2cli.core.config import CONFIG

    try:
        artifact = Result.load(artifact_path)
        _cache = Cache(cache)
        _cache.save(artifact, key)
    except Exception as e:
        header = "There was a problem saving the artifact '%s' to the cache " \
                 "'%s' under the key '%s':" % (artifact_path, cache, key)
        q2cli.util.exit_with_error(e, header=header, traceback=None)

    success = "Saved the artifact '%s' to the cache '%s' under the key " \
        "'%s'" % (artifact_path, cache, key)
    click.echo(CONFIG.cfg_style('success', success))


@tools.command(name='cache-fetch',
               short_help='Fetches an artifact out of a cache into a .qza.',
               help='Fetches the artifact saved to the specified cache under '
                    'the specified key into a .qza at the specified location.',
               cls=ToolCommand)
@click.option('--cache', required=True,
              type=click.Path(exists=True, file_okay=False, dir_okay=True,
                              readable=True),
              help='Path to an existing cache to load from.')
@click.option('--key', required=True,
              help='The key to the artifact being loaded.')
@click.option('--output-path', required=True,
              type=click.Path(exists=False, readable=True),
              help='Path to put the .qza we are loading the artifact into.')
def cache_fetch(cache, key, output_path):
    from qiime2.core.cache import Cache
    from q2cli.core.config import CONFIG

    try:
        _cache = Cache(cache)
        artifact = _cache.load(key)
        artifact.save(output_path)
    except Exception as e:
        header = "There was a problem loading the artifact with the key " \
                 "'%s' from the cache '%s' and saving it to the file '%s':" % \
                 key, cache, output_path
        q2cli.util.exit_with_error(e, header=header, traceback=None)

    success = "Loaded artifact with the key '%s' from the cache '%s' and " \
        "saved it to the file '%s'" % (key, cache, output_path)
    click.echo(CONFIG.cfg_style('success', success))


@tools.command(name='cache-status',
               short_help='Checks the status of the cache.',
               help='Lists all keys in the given cache. Peeks artifacts '
                    'pointed to by keys to data and lists the number of '
                    'artifacts in the pool for keys to pools.',
               cls=ToolCommand)
@click.option('--cache', required=True,
              type=click.Path(exists=True, file_okay=False, dir_okay=True,
                              readable=True),
              help='Path to an existing cache to check the status of.')
def cache_status(cache):
    from qiime2.core.cache import Cache
    from qiime2.sdk.result import Result

    from q2cli.core.config import CONFIG

    data_output = []
    pool_output = []
    try:
        _cache = Cache(cache)
        with _cache.lock:
            for key in _cache.get_keys():
                key_values = _cache.read_key(key)

                if (data := key_values['data']) is not None:
                    data_output.append(
                        'data: %s -> %s' %
                        (key, str(Result.peek(_cache.data / data))))
                elif (pool := key_values['pool']) is not None:
                    pool_output.append(
                        'pool: %s -> size = %s' %
                        (key, str(len(os.listdir(_cache.pools / pool)))))
    except Exception as e:
        header = "There was a problem getting the status of the cache at " \
                 "path '%s':" % cache
        q2cli.util.exit_with_error(e, header=header, traceback=None)

    if not data_output:
        data_output = 'No data keys in cache'
    else:
        data_output = '\n'.join(data_output)
        data_output = 'Data keys in cache:\n' + data_output

    if not pool_output:
        pool_output = 'No pool keys in cache'
    else:
        pool_output = '\n'.join(pool_output)
        pool_output = 'Pool keys in cache:\n' + pool_output

    output = data_output + '\n\n' + pool_output
    success = "Status of the cache at the path '%s':\n\n%s" % \
        (cache, output)
    click.echo(CONFIG.cfg_style('success', success))
