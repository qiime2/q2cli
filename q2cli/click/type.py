# ----------------------------------------------------------------------------
# Copyright (c) 2016-2022, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import click


def is_writable_dir(path):
    import os

    head = 'do-while'
    path = os.path.normpath(os.path.abspath(path))
    while head:
        if os.path.exists(path):
            if os.path.isfile(path):
                return False
            else:
                return os.access(path, os.W_OK | os.X_OK)
        path, head = os.path.split(path)

    return False


class OutDirType(click.Path):
    def convert(self, value, param, ctx):
        import os
        # Click path fails to validate writability on new paths

        if os.path.exists(value):
            if os.path.isfile(value):
                self.fail('%r is already a file.' % (value,), param, ctx)
            else:
                self.fail('%r already exists, will not overwrite.' % (value,),
                          param, ctx)

        if value[-1] != os.path.sep:
            value += os.path.sep

        if not is_writable_dir(value):
            self.fail('%r is not a writable directory, cannot write output'
                      ' to it.' % (value,), param, ctx)
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
        from q2cli.util import output_in_cache
        # Click path fails to validate writability on new paths

        # Check if our output path is actually in a cache and if it is skip our
        # other checks
        if output_in_cache(value):
            return value

        if os.path.exists(value):
            if os.path.isdir(value):
                self.fail('%r is already a directory.' % (value,), param, ctx)

        directory = os.path.dirname(value)
        if directory and not os.path.exists(directory):
            self.fail('Directory %r does not exist, cannot save %r into it.'
                      % (directory, os.path.basename(value)), param, ctx)

        if not is_writable_dir(directory):
            self.fail('%r is not a writable directory, cannot write output'
                      ' to it.' % (directory,), param, ctx)
        return value

    def _convert_input(self, value, param, ctx):
        import os
        import qiime2.sdk
        import qiime2.sdk.util
        import q2cli.util

        try:
            result, error = q2cli.util._load_input(value)
        except Exception as e:
            header = f'There was a problem loading {value!r} as an artifact:'
            q2cli.util.exit_with_error(
                e, header=header, traceback='stderr')

        if error:
            self.fail(str(error), param, ctx)
        # We want to use click's fail to pretty print whatever error we got
        # from get_input

        if isinstance(result, qiime2.sdk.Visualization):
            maybe = value[:-1] + 'a'
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
        import q2cli.util

        if self.type_expr.name == 'MetadataColumn':
            value, column = value

        metadata = q2cli.util.load_metadata(value)

        if self.type_expr.name != 'MetadataColumn':
            return metadata
        else:
            try:
                metadata_column = metadata.get_column(column)
            except Exception:
                self.fail("There was an issue with retrieving column %r from "
                          "the metadata." % column)

            if metadata_column not in self.type_expr:
                self.fail("Metadata column is of type %r, but expected %r."
                          % (metadata_column.type, self.type_expr.fields[0]))

            return metadata_column

    def _convert_primitive(self, value, param, ctx):
        import qiime2.sdk.util

        try:
            return qiime2.sdk.util.parse_primitive(self.type_expr, value)
        except ValueError:
            expr = qiime2.sdk.util.type_from_ast(self.type_ast)
            raise click.BadParameter(
                'received <%s> as an argument, which is incompatible'
                ' with parameter type: %r' % (value, expr),
                ctx=ctx)

    @property
    def name(self):
        return self.get_metavar('')

    def get_type_repr(self, param):
        return self.type_repr

    def get_missing_message(self, param):
        if self.is_output:
            return '("--output-dir" may also be used)'
