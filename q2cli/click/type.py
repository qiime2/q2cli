# ----------------------------------------------------------------------------
# Copyright (c) 2016-2019, QIIME 2 development team.
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


class ControlFlowException(Exception):
    pass


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

        directory = os.path.dirname(value)
        if not is_writable_dir(directory):
            self.fail('%r is not a writable directory, cannot write output'
                      ' to it.' % (directory,), param, ctx)
        return value

    def _convert_input(self, value, param, ctx):
        import os
        import tempfile
        import qiime2.sdk
        import qiime2.sdk.util

        try:
            try:
                result = qiime2.sdk.Result.load(value)
            except OSError as e:
                if e.errno == 28:
                    temp = tempfile.tempdir
                    self.fail(f'There was not enough space left on {temp!r} '
                              f'to extract the artifact {value!r}. '
                              '(Try setting $TMPDIR to a directory with '
                              'more space, or increasing the size of '
                              f'{temp!r})', param, ctx)
                else:
                    raise ControlFlowException
            except ValueError as e:
                if 'does not exist' in str(e):
                    self.fail(f'{value!r} is not a valid filepath', param, ctx)
                else:
                    raise ControlFlowException
            except Exception:
                raise ControlFlowException
        except ControlFlowException:
            self.fail('%r is not a QIIME 2 Artifact (.qza)' % value, param,
                      ctx)

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
            except Exception:
                self.fail("There was an issue with retrieving column %r from "
                          "the metadata:" % column)

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

    def get_type_repr(self, param):
        return self.type_repr

    def get_missing_message(self, param):
        if self.is_output:
            return '("--output-dir" may also be used)'
