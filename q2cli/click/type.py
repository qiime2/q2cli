import click

class OutDirType(click.Path):
    def convert(self, value, param, ctx):
        import os
        # Click path fails to validate writability on new paths

        if os.path.exists(value):
            if os.path.isfile(value):
                self.fail('%r is already a file.' % (value,), param, ctx)

        if value[-1] != os.path.sep:
            value += os.path.sep

        directory = os.path.abspath(os.path.dirname(value))
        if not os.access(directory, os.W_OK | os.X_OK):
            self.fail('%r is not a writable directory, cannot write output'
                      ' to it.' % (directory,), param, ctx)
        return value


class QIIME2Type(click.ParamType):
    def __init__(self, type_ast, type_repr, is_output=False):
        self.type_repr = type_repr
        self.type_ast = type_ast
        self.is_output = is_output
        self._type_expr = None

    @property
    def type_expr(self):
        import qiime2.sdk.util

        if self._type_expr is None:
            self._type_expr = qiime2.sdk.util.type_from_ast(self.type_ast)
        return self._type_expr

    def convert(self, value, param, ctx):
        import qiime2.sdk.util

        if value is None:
            return None  # Them's the rules

        if self.is_output:
            return self._convert_output(value, param, ctx)

        if qiime2.sdk.util.is_semantic_type(self.type_expr):
            return self._convert_input(value, param, ctx)

        if qiime2.sdk.util.is_metadata_type(self.type_expr):
            return self._convert_metadata(value, param, ctx)

        return self._convert_primitive(value, param, ctx)

    def _convert_output(self, value, param, ctx):
        import os
        # Click path fails to validate writability on new paths

        if os.path.exists(value):
            if os.path.isdir(value):
                self.fail('%r is already a directory.' % (value,), param, ctx)

        directory = os.path.abspath(os.path.dirname(value))
        if not os.access(directory, os.W_OK | os.X_OK):
            self.fail('%r is not a writable directory, cannot write output'
                      ' to it.' % (directory,), param, ctx)
        return value


    def _convert_input(self, value, param, ctx):
        import os
        import qiime2.sdk
        import qiime2.sdk.util

        try:
            result = qiime2.sdk.Result.load(value)
        except Exception:
            self.fail('%r is not a QIIME 2 Artifact (.qza)' % value,
                      param, ctx)

        if isinstance(result, qiime2.sdk.Visualization):
            maybe = value[:-1]  + 'a'
            hint = ''
            if os.path.exists(maybe):
                hint = ('  (There is an artifact with the same name:'
                        ' %r, did you mean that?)'
                        % os.path.basename(maybe))

            self.fail('%r is a QIIME 2 visualization (.qzv), not an '
                      ' Artifact (.qza)%s' % (value, hint), param, ctx)

        style = qiime2.sdk.util.interrogate_collection_type(self.type_expr)
        if style.style is None and result not in self.type_expr:
            # collections need to be handled above this
            self.fail("Expected an artifact of at least type %r."
                      " An artifact of type %r was provided."
                      % (self.type_expr, result.type), param, ctx)

        return result

    def _convert_metadata(self, value, param, ctx):
        import sys
        import qiime2
        import q2cli.util

        if self.type_expr.name == 'MetadataColumn':
            value, column = value
        fp = value

        try:
            artifact = qiime2.Artifact.load(fp)
        except Exception:
            try:
                metadata = qiime2.Metadata.load(fp)
            except Exception as e:
                header = ("There was an issue with loading the file %s as "
                          "metadata:" % fp)
                tb = 'stderr' if '--verbose' in sys.argv else None
                q2cli.util.exit_with_error(e, header=header, traceback=tb)
        else:
            try:
                metadata = artifact.view(qiime2.Metadata)
            except Exception as e:
                header = ("There was an issue with viewing the artifact "
                          "%s as QIIME 2 Metadata:" % fp)
                tb = 'stderr' if '--verbose' in sys.argv else None
                q2cli.util.exit_with_error(e, header=header, traceback=tb)

        if self.type_expr.name != 'MetadataColumn':
            return metadata
        else:
            try:
                metadata_column = metadata.get_column(column)
            except Exception as e:
                self.fail("There was an issue with retrieving column %r from "
                          "the metadata:" % column_value)

            if metadata_column not in self.type_expr:
                self.fail("Metadata column is of type %r, but expected %r."
                          % (metadata_column.type, self.type_expr.fields[0]))

            return metadata_column


    def _convert_primitive(self, value, param, ctx):
        import qiime2.sdk.util

        return qiime2.sdk.util.parse_primitive(self.type_expr, value)

    @property
    def name(self):
        return self.get_metavar('')

    def get_metavar(self, param):
        import qiime2.sdk.util

        name_to_var = {
            'Visualization': 'VISUALIZATION',
            'Int': 'INTEGER',
            'Str': 'TEXT',
            'Float': 'NUMBER',
            'Bool': '',
        }

        style = qiime2.sdk.util.interrogate_collection_type(self.type_expr)

        multiple = style.style is not None
        if style.style == 'simple':
            inner_type = style.members
        elif not multiple:
            inner_type = self.type_expr
        else:
            inner_type = None

        if qiime2.sdk.util.is_semantic_type(self.type_expr):
            metavar = 'ARTIFACT'
        elif qiime2.sdk.util.is_metadata_type(self.type_expr):
            metavar = 'METADATA'
        elif style.style is not None and style.style != 'simple':
            metavar = 'VALUE'
        else:
            metavar = name_to_var[inner_type.name]
        if (metavar == 'NUMBER' and inner_type is not None
                and inner_type.predicate is not None
                and inner_type.predicate.template.start == 0
                and inner_type.predicate.template.end == 1):
            metavar = 'PROPORTION'

        if multiple or self.type_expr.name == 'Metadata':
            if metavar != 'TEXT' and metavar != '' and metavar != 'METADATA':
                metavar += 'S'
            metavar += '...'

        return metavar

    def get_type_repr(self, param):
        import qiime2.sdk.util

        type_repr = self.type_repr
        metavar = self.get_metavar(param)
        style = qiime2.sdk.util.interrogate_collection_type(self.type_expr)

        if not metavar.startswith('ARTIFACT'):
            if style.style is None:
                if style.expr.predicate is not None:
                    type_repr = repr(style.expr.predicate)
                elif not self.type_expr.fields:
                    type_repr = None
            elif style.style == 'simple':
                if style.members.predicate is not None:
                    type_repr = repr(style.members.predicate)

        return type_repr

    def get_missing_message(self, param):
        if self.is_output:
            return '("--output-dir" may also be used)'

