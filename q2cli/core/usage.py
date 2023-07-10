# ----------------------------------------------------------------------------
# Copyright (c) 2016-2023, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import collections
import os
import shlex
import textwrap

import qiime2.sdk.usage as usage
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
        # it would be nice to have a / as the 'ext' for collections so that
        # it's clear that it's a directory, but that's proving to be a pain
        # so putting on hold for now
        'result_collection': '/',
        'visualization': '.qzv',
        'metadata': '.tsv',
        'column': '',
        'format': '',
    }

    @property
    def ext(self):
        return self.EXT[self.var_type]

    @staticmethod
    def to_cli_name(val):
        return util.to_cli_name(val)

    def to_interface_name(self):
        if hasattr(self, '_q2cli_ref'):
            return self._q2cli_ref

        cli_name = '%s%s' % (self.name, self.ext)

        # don't disturb file names, this will break importing where QIIME 2
        # relies on specific filenames being present in a dir
        if self.var_type not in ('format', 'column'):
            cli_name = self.to_cli_name(cli_name)

        return cli_name

    def assert_has_line_matching(self, path, expression):
        if not self.use.enable_assertions:
            return

        INDENT = self.use.INDENT
        input_path = self.to_interface_name()
        expr = shlex.quote(expression)

        lines = [
            'qiime dev assert-result-data %s \\' % (input_path,),
            INDENT + '--zip-data-path %s \\' % (path,),
            INDENT + '--expression %s' % (expr,),
        ]

        self.use.recorder.extend(lines)

    def assert_output_type(self, semantic_type):
        if not self.use.enable_assertions:
            return

        INDENT = self.use.INDENT
        input_path = self.to_interface_name()

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

    def init_result_collection(self, name, factory):
        variable = super().init_result_collection(name, factory)

        self.init_data.append(variable)

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
