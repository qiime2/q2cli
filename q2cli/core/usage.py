# ----------------------------------------------------------------------------
# Copyright (c) 2016-2023, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import collections
import os
import pkg_resources
import re
import shlex
import textwrap
from typing import Any, Callable, Dict, List, Tuple

from qiime2 import ResultCollection
import qiime2.sdk.usage as usage
from qiime2.sdk.usage import (
    UsageVariable, Usage, UsageInputs, UsageOutputs, UsageOutputNames
)
from qiime2.sdk import Action
from qiime2.core.archive.provenance_lib.usage_drivers import (
    build_header, build_footer
)
from qiime2.core.archive.provenance_lib import ProvDAG

import q2cli.util as util
from q2cli.core.state import get_action_state
import q2cli.click.option


def write_example_data(action, output_dir):
    for example_name, example in action.examples.items():
        cli_name = util.to_cli_name(example_name)
        example_path = os.path.join(output_dir, cli_name)

        use = CLIUsage()
        example(use)

        for fn, val in use.get_example_data():
            os.makedirs(example_path, exist_ok=True)
            path = os.path.join(example_path, fn)
            val.save(path)
            try:
                hint = repr(val.type)
            except AttributeError:
                hint = 'Metadata'

            yield hint, path


def write_plugin_example_data(plugin, output_dir):
    for name, action in plugin.actions.items():
        path = os.path.join(output_dir, util.to_cli_name(name))

        yield from write_example_data(action, path)


class CLIUsageVariable(usage.UsageVariable):
    EXT = {
        'artifact': '.qza',
        'artifact_collection': '/',
        'visualization_collection': '/',
        'visualization': '.qzv',
        'metadata': '.tsv',
        'column': '',
        'format': '',
    }

    ELEMENT_EXT = {
        'artifact_collection': EXT['artifact'],
        'visualization_collection': EXT['visualization']
    }

    @property
    def ext(self):
        return self.EXT[self.var_type]

    @staticmethod
    def to_cli_name(val):
        return util.to_cli_name(val)

    def _key_helper(self, input_path, key):
        if self.var_type not in self.COLLECTION_VAR_TYPES:
            raise KeyboardInterrupt(
                f'Cannot key non-collection type {self.var_type}')

        return "%s%s%s" % (input_path, key, self.ELEMENT_EXT[self.var_type])

    def to_interface_name(self):
        if hasattr(self, '_q2cli_ref'):
            return self._q2cli_ref

        cli_name = '%s%s' % (self.name, self.ext)

        # don't disturb file names, this will break importing where QIIME 2
        # relies on specific filenames being present in a dir
        if self.var_type not in ('format', 'column'):
            cli_name = self.to_cli_name(cli_name)

        return cli_name

    def assert_has_line_matching(self, path, expression, key=None):
        if not self.use.enable_assertions:
            return

        INDENT = self.use.INDENT
        input_path = self.to_interface_name()
        expr = shlex.quote(expression)

        if key:
            input_path = self._key_helper(input_path, key)

        lines = [
            'qiime dev assert-result-data %s \\' % (input_path,),
            INDENT + '--zip-data-path %s \\' % (path,),
            INDENT + '--expression %s' % (expr,),
        ]

        self.use.recorder.extend(lines)

    def assert_output_type(self, semantic_type, key=None):
        if not self.use.enable_assertions:
            return

        INDENT = self.use.INDENT
        input_path = self.to_interface_name()

        if key:
            input_path = self._key_helper(input_path, key)

        lines = [
            'qiime dev assert-result-type %s \\' % (input_path,),
            INDENT + '--qiime-type %s' % (str(semantic_type),),
        ]

        self.use.recorder.extend(lines)


class CLIUsage(usage.Usage):
    INDENT = ' ' * 2

    def __init__(self, enable_assertions=False, action_collection_size=None):
        super().__init__()
        self.recorder = []
        self.init_data = []
        self.enable_assertions = enable_assertions
        self.action_collection_size = action_collection_size
        self.output_dir_counter = collections.defaultdict(int)

    def usage_variable(self, name, factory, var_type):
        return CLIUsageVariable(name, factory, var_type, self)

    def render(self, flush=False):
        rendered = '\n'.join(self.recorder)
        if flush:
            self.recorder = []
            self.init_data = []
        return rendered

    def init_artifact(self, name, factory):
        variable = super().init_artifact(name, factory)

        self.init_data.append(variable)

        return variable

    def init_artifact_collection(self, name, factory):
        variable = super().init_artifact_collection(name, factory)

        self.init_data.append(variable)

        return variable

    def construct_artifact_collection(self, name, members):
        variable = super().construct_artifact_collection(
            name, members
        )

        str_namespace = {str(name) for name in self.namespace}
        diff = set(
            member.to_interface_name() for member in members.values()
        ) - str_namespace
        if diff:
            msg = (
                f'{diff} not found in driver\'s namespace. Make sure '
                'that all ResultCollection members have been properly '
                'created.'
            )
            raise ValueError(msg)

        rc_dir = variable.to_interface_name()

        keys = members.keys()
        names = [name.to_interface_name() for name in members.values()]

        keys_arg = '( '
        for key in keys:
            keys_arg += f'{key} '
        keys_arg += ')'
        names_arg = '( '
        for name in names:
            names_arg += f'{name} '
        names_arg += ')'

        lines = [
            '## constructing result collection ##',
            f'rc_name={rc_dir}',
            'ext=.qza',
            f'keys={keys_arg}',
            f'names={names_arg}',
            'construct_result_collection',
            '##',
        ]
        self.recorder.extend(lines)

        return variable

    def get_artifact_collection_member(self, name, variable, key):
        accessed_variable = super().get_artifact_collection_member(
            name, variable, key
        )

        rc_dir = variable.to_interface_name()
        member_fp = os.path.join(rc_dir, f'{key}.qza')

        lines = [
            '## accessing result collection member ##',
            f'ln -s {member_fp} {accessed_variable.to_interface_name()}',
            '##',
        ]
        self.recorder.extend(lines)

        return variable

    def import_from_format(self, name, semantic_type,
                           variable, view_type=None):
        imported_var = super().import_from_format(
            name, semantic_type, variable, view_type=view_type)

        in_fp = variable.to_interface_name()
        out_fp = imported_var.to_interface_name()

        lines = [
            'qiime tools import \\',
            self.INDENT + '--type %r \\' % (semantic_type,)
        ]

        if view_type is not None:
            if type(view_type) is not str:
                view_type = view_type.__name__
            lines.append(self.INDENT + '--input-format %s \\' % (view_type,))

        lines += [
            self.INDENT + '--input-path %s \\' % (in_fp,),
            self.INDENT + '--output-path %s' % (out_fp,),
        ]

        self.recorder.extend(lines)

        return imported_var

    def init_format(self, name, factory, ext=None):
        if ext is not None:
            name = '%s.%s' % (name, ext.lstrip('.'))

        variable = super().init_format(name, factory, ext=ext)

        self.init_data.append(variable)

        return variable

    def init_metadata(self, name, factory):
        variable = super().init_metadata(name, factory)

        self.init_data.append(variable)

        return variable

    def comment(self, text):
        self.recorder += ['# ' + ln for ln in textwrap.wrap(text, width=74)]

    def peek(self, variable):
        var_name = variable.to_interface_name()
        self.recorder.append('qiime tools peek %s' % var_name)

    def merge_metadata(self, name, *variables):
        var = super().merge_metadata(name, *variables)

        # this is our special "short-circuit" attr to handle special-case
        # .to_interface_name() needs
        var._q2cli_ref = ' '.join(v.to_interface_name() for v in variables)
        return var

    def get_metadata_column(self, name, column_name, variable):
        var = super().get_metadata_column(name, column_name, variable)

        # this is our special "short-circuit" attr to handle special-case
        # .to_interface_name() needs
        var._q2cli_ref = (variable.to_interface_name(), column_name)
        return var

    def view_as_metadata(self, name, variable):
        # use the given name so that namespace behaves as expected,
        # then overwrite it because viewing is a no-op in q2cli
        var = super().view_as_metadata(name, variable)
        # preserve the original interface name of the QZA as this will be
        # implicitly converted to metadata when executed.
        var._q2cli_ref = variable.to_interface_name()
        return var

    def action(self, action, inputs, outputs):
        variables = super().action(action, inputs, outputs)

        vars_dict = variables._asdict()

        plugin_name = util.to_cli_name(action.plugin_id)
        action_name = util.to_cli_name(action.action_id)
        self.recorder.append('qiime %s %s \\' % (plugin_name, action_name))

        action_f = action.get_action()
        action_state = get_action_state(action_f)

        ins = inputs.map_variables(lambda v: v.to_interface_name())
        outs = {k: v.to_interface_name() for k, v in vars_dict.items()}
        signature = {s['name']: s for s in action_state['signature']}

        for param_name, value in ins.items():
            self._append_action_line(signature, param_name, value)

        max_collection_size = self.action_collection_size
        if max_collection_size is not None and len(outs) > max_collection_size:
            dir_name = self._build_output_dir_name(plugin_name, action_name)
            self.recorder.append(
                self.INDENT + '--output-dir %s \\' % (dir_name))
            self._rename_outputs(vars_dict, dir_name)
        else:
            for param_name, value in outs.items():
                self._append_action_line(signature, param_name, value)

        self.recorder[-1] = self.recorder[-1][:-2]  # remove trailing \

        return variables

    def _build_output_dir_name(self, plugin_name, action_name):
        base_name = '%s-%s' % (plugin_name, action_name)
        self.output_dir_counter[base_name] += 1
        current_inc = self.output_dir_counter[base_name]
        if current_inc == 1:
            return base_name
        return '%s-%d' % (base_name, current_inc)

    def _rename_outputs(self, vars_dict, dir_name):
        for signature_name, variable in vars_dict.items():
            name = '%s%s' % (signature_name, variable.ext)
            variable._q2cli_ref = os.path.join(dir_name, name)

    def _append_action_line(self, signature, param_name, value):
        param_state = signature[param_name]
        if value is not None:
            for opt, val in self._make_param(value, param_state):
                line = self.INDENT + opt
                if val is not None:
                    line += ' ' + val
                line += ' \\'

                self.recorder.append(line)

    def _make_param(self, value, state):
        state = state.copy()
        type_ = state.pop('type')

        opt = q2cli.click.option.GeneratedOption(prefix=type_[0], **state)
        option = opt.opts[0]

        # INPUTS AND OUTPUTS
        if type_ in ('input', 'output'):
            if isinstance(value, str):
                return [(option, value)]
            else:
                if isinstance(value, set):
                    value = sorted(value)
                return [(option, ' '.join(value))]

        # METADATA FILE
        if state['metadata'] == 'file':
            return [(option, value)]

        # METADATA COLUMN
        if state['metadata'] == 'column':
            # md cols are special, we have pre-computed the interface-specific
            # names and stashed them in an attr, so unpack to get the values
            fn, col_name = value
            return [(option, fn), (opt.q2_extra_opts[0], col_name)]

        # PARAMETERS
        if type_ == 'parameter':
            if isinstance(value, set):
                value = [shlex.quote(str(v)) for v in value]
                return [(option, ' '.join(sorted(value)))]

            if isinstance(value, list):
                return [(option, ' '.join(shlex.quote(str(v)) for v in value))]

            if isinstance(value, (dict, ResultCollection)):
                return [(option, ' '.join(f'{k}:{shlex.quote(str(v))}'
                                          for k, v in value.items()))]

            if type(value) is bool:
                if state['ast']['type'] == 'expression':
                    if value:
                        return [(option, None)]
                    else:
                        return [(opt.secondary_opts[0], None)]
                else:
                    # This is a more complicated param that can't be expressed
                    # as a typical `--p-foo/--p-no-foo` so default to baseline
                    # parameter handling behavior.
                    pass

            if type(value) is str:
                return [(option, shlex.quote(value))]

            return [(option, str(value))]

        raise Exception('Something went terribly wrong!')

    def get_example_data(self):
        for val in self.init_data:
            yield val.to_interface_name(), val.execute()


class ReplayCLIUsageVariable(CLIUsageVariable):
    def to_interface_name(self):
        '''
        Differs from parent method in that metadata is not kebab-cased,
        filepaths are preserved instead.
        '''
        if hasattr(self, '_q2cli_ref'):
            return self._q2cli_ref

        cli_name = '%s%s' % (self.name, self.ext)

        # don't disturb file names, this will break importing where QIIME 2
        # relies on specific filenames being present in a dir
        if self.var_type not in ('format', 'column', 'metadata'):
            cli_name = self.to_cli_name(cli_name)

        return cli_name


class ReplayCLIUsage(CLIUsage):
    shebang = '#!/usr/bin/env bash'
    header_boundary = ('#' * 79)
    set_ex = [
        '# This tells bash to -e exit immediately if a command fails',
        '# and -x show all commands in stdout so you can track progress',
        'set -e -x',
        ''
    ]
    copyright = pkg_resources.resource_string(
        __package__, 'assets/copyright_note.txt'
    ).decode('utf-8').split('\n')
    how_to = pkg_resources.resource_string(
        __package__, 'assets/cli_howto.txt'
    ).decode('utf-8').split('\n')

    def __init__(self, enable_assertions=False, action_collection_size=None):
        '''
        Identical to parent but creates header and footer attributes.

        Parameters
        ----------
        enable_assertions : bool
            Whether to render has-line-matching and output type assertions.
        action_collection_size : int
            The number of outputs returned by an action above which outputs are
            grouped into and accessed from an --output-dir.
        '''
        super().__init__()
        self.header = []
        self.footer = []
        self.enable_assertions = enable_assertions
        self.action_collection_size = action_collection_size

    def usage_variable(self, name, factory, var_type):
        return ReplayCLIUsageVariable(name, factory, var_type, self)

    def _append_action_line(self, signature, param_name: str, value):
        '''
        Extends the parent method to accommodate action signatures that may
        differ between those found in provenance and those accessible in the
        currently executing environment.

        Parameters
        ----------
        signature : dict of str -> dict
            Mapping of name of signature item to dict of signature spec data.
        param_name : str
            The name of the parameter for which to render a CLI line.
        value : any
            The value of an item from a Results.
        '''
        param_state = signature.get(param_name)
        if param_state is not None:
            for opt, val in self._make_param(value, param_state):
                line = self.INDENT + opt
                if val is not None:
                    line += ' ' + val
                line += ' \\'
                self.recorder.append(line)
        else:  # no matching param name
            line = self.INDENT + (
                '# FIXME: The following parameter name was not found in '
                'your current\n  # QIIME 2 environment. This may occur '
                'when the plugin version you have\n  # installed does not '
                'match the version used in the original analysis.\n  # '
                'Please see the docs and correct the parameter name '
                'before running.\n')
            cli_name = re.sub('_', '-', param_name)
            line += self.INDENT + '--?-' + cli_name + ' ' + str(value)
            line += ' \\'
            self.recorder.append(line)

    def _make_param(self, value: Any, state: Dict) -> List[Tuple]:
        '''
        Wraps metadata filenames in <> to force users to replace them.

        Parameters
        ----------
        value : any
            A value of a Result.
        state : dict
             A collection of info about an item from an action signature.
             See q2cli.core.state.py.

        Returns
        -------
        list of tuple
            See q2cli.core.usage.CLIUsage._make_param for possible outputs.
        '''
        if state['metadata'] == 'column':
            value = (f'{value[0]}', *value[1:])
        if state['metadata'] == 'file':
            value = f'{value}'
        return super()._make_param(value, state)

    def import_from_format(
        self,
        name: str,
        semantic_type: str,
        variable: UsageVariable,
        view_type: Any = None
    ) -> UsageVariable:
        '''
        Identical to super.import_from_format, but writes
        --input-path <yourdata here> and follows import block with a
        blank line.

        Parameters
        ----------
        name : str
            The name of the created UsageVariable.
        semantic_type : str
            The semantic type of the created UsageVariable.
        variable : UsageVariable
            A UsageVariable of some format type that will materialize the
            data to be imported.
        view_type : format or str
            The view type for importing.

        Returns
        -------
        UsageVariable
            Of type artifact.
        '''
        # need the super().super() here, so pass self to super
        imported_var = Usage.import_from_format(
            self, name, semantic_type, variable, view_type=view_type
        )

        out_fp = imported_var.to_interface_name()

        lines = [
            'qiime tools import \\',
            self.INDENT + '--type %r \\' % (semantic_type,)
        ]

        if view_type is not None:
            lines.append(
                self.INDENT + '--input-format %s \\' % (view_type,)
            )

        lines += [
            self.INDENT + '--input-path <your data here> \\',
            self.INDENT + '--output-path %s' % (out_fp,),
        ]

        lines.append('')
        self.recorder.extend(lines)

        return imported_var

    def init_metadata(
        self, name: str, factory: Callable, dumped_md_fn: str = ''
    ) -> UsageVariable:
        '''
        Like parent, but appropriately handles filepaths for recorded md fps.

        Parameters
        ----------
        name : str
            The name of the UsageVariable to be created.
        factory : Callable
            The factory responsible for generating the realized value of the
            UsageVariable.

        Returns
        -------
        UsageVariable
            Of type metadata.
        '''
        variable = super().init_metadata(name, factory)

        self.init_data.append(variable)

        if dumped_md_fn:
            variable.name = f'"{dumped_md_fn}.tsv"'
        else:
            variable.name = '<your metadata filepath>'

        return variable

    def comment(self, text):
        '''
        Identical to parent method, but pads comments with an extra newline.
        '''
        super().comment(text)
        self.recorder.append('')

    def action(
        self,
        action: Action,
        inputs: UsageInputs,
        outputs: UsageOutputNames
    ) -> UsageOutputs:
        '''
        Overrides parent method to fill in missing outputlines from
        action_f.signature.
        Also pads actions with an extra newline.

        Parameters
        ----------
        action : Action
            The underlying sdk.Action object.
        inputs : UsageInputs
            Mapping of parameter names to arguments for the action.
        outputs : UsageOutputNames
            Mapping of registered output names to usage variable names.

        Returns
        -------
        UsageOutputs
            The results returned by the action.
        '''
        variables = Usage.action(self, action, inputs, outputs)
        vars_dict = variables._asdict()

        # get registered collection of output names so we don't miss any
        action_f = action.get_action()
        missing_outputs = {}
        for output in action_f.signature.outputs:
            try:
                # If we get a match on output-name, the correct pair is already
                # in vars_dict and we can continue
                getattr(variables, output)
            except AttributeError:
                # Otherwise, we should add filler values to missing_outputs
                missing_outputs[output] = f'XX_{output}'

        plugin_name = q2cli.util.to_cli_name(action.plugin_id)
        action_name = q2cli.util.to_cli_name(action.action_id)
        self.recorder.append('qiime %s %s \\' % (plugin_name, action_name))

        action_f = action.get_action()
        action_state = get_action_state(action_f)

        ins = inputs.map_variables(lambda v: v.to_interface_name())
        outs = {k: v.to_interface_name() for k, v in vars_dict.items()}
        outs.update(missing_outputs)
        signature = {s['name']: s for s in action_state['signature']}

        for param_name, value in ins.items():
            self._append_action_line(signature, param_name, value)

        max_collection_size = self.action_collection_size
        if max_collection_size is not None and len(outs) > max_collection_size:
            dir_name = self._build_output_dir_name(plugin_name, action_name)
            self.recorder.append(
                self.INDENT + '--output-dir %s \\' % (dir_name)
            )
            self._rename_outputs(vars_dict, dir_name)
        else:
            for param_name, value in outs.items():
                self._append_action_line(signature, param_name, value)

        self.recorder[-1] = self.recorder[-1][:-2]  # remove trailing `\`

        self.recorder.append('')
        return variables

    def render(self, flush=False):
        '''
        Return a newline-seperated string of CLI script.

        Parameters
        ----------
        flush : bool
            Whether to 'flush' the current code. Importantly, this will clear
            the top-line imports for future invocations.

        Returns
        -------
        str
            The rendered string of CLI code.
        '''
        if self.header:
            self.header = self.header + ['']
        if self.footer:
            self.footer = [''] + self.footer
        rendered = '\n'.join(
            self.header + self.set_ex + self.recorder + self.footer
        )
        if flush:
            self.header = []
            self.footer = []
            self.recorder = []
            self.init_data = []
        return rendered

    def build_header(self):
        '''Constructs a renderable header from its components.'''
        self.header.extend(build_header(
            self.shebang, self.header_boundary, self.copyright, self.how_to
        ))

        # for creating result collections in bash
        bash_rc_function = [
            'construct_result_collection () {',
            '\tmkdir $rc_name',
            '\ttouch $rc_name.order',
            '\tfor key in "${keys[@]}"; do',
            '\t\techo $key >> $rc_name.order',
            '\tdone',
            '\tfor i in "${!keys[@]}"; do',
            '\t\tln -s ../"${names[i]}" $rc_name"${keys[i]}"$ext',
            '\tdone',
            '}'
        ]
        self.header.extend([
            '## function to create result collections ##',
            *bash_rc_function,
            '##',
        ])

    def build_footer(self, dag: ProvDAG):
        '''
        Constructs a renderable footer using the terminal uuids of a ProvDAG.
        '''
        self.footer.extend(build_footer(dag, self.header_boundary))
