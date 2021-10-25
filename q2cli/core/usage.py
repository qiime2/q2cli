# ----------------------------------------------------------------------------
# Copyright (c) 2016-2021, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

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

        use = CLIUsageFormatter()
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
    def to_interface_name(self):
        ext = {
            'artifact': '.qza',
            'visualization': '.qzv',
            'metadata': '.tsv',
            'column': '',
        }[self.var_type]

        cli_name = util.to_cli_name(self.name)
        fn = '%s%s' % (cli_name, ext)
        return shlex.quote(fn)

    def assert_has_line_matching(self, path, expression):
        if self.use.enable_assertions:
            self.use.lines.append(
                'qiime dev assert-result-data %s --zip-data-path %s'
                ' --expression %s' %
                (self.to_interface_name(), path, shlex.quote(expression)))

    def assert_output_type(self, semantic_type):
        if self.use.enable_assertions:
            self.use.lines.append(
                'qiime dev assert-result-type %s'
                ' --qiime-type %s' %
                (self.to_interface_name(), shlex.quote(str(semantic_type))))


class CLIUsageFormatter(usage.Usage):
    INDENT = ' ' * 2

    def __init__(self, enable_assertions=False):
        super().__init__()
        self.lines = []
        self.init_data = []
        self.enable_assertions = enable_assertions

    def get_example_data(self):
        for val in self.init_data:
            yield val.to_interface_name(), val.execute()

    def variable_factory(self, name, factory, var_type):
        return CLIUsageVariable(
            name,
            factory,
            var_type,
            self,
        )

    def init_artifact(self, name, factory):
        variable = super().init_artifact(name, factory)
        self.init_data.append(variable)
        return variable

    def init_metadata(self, name, factory):
        variable = super().init_metadata(name, factory)
        self.init_data.append(variable)
        return variable

    def comment(self, text: str):
        self.lines += ['# ' + line for line in textwrap.wrap(text, width=74)]

    # TODO: add example for viewing qza as md
    def merge_metadata(self, name, *variables):
        _ = super().merge_metadata(name, *variables)
        # rather than returning a new CLIUsageVariable, we return the
        # collection of CLIUsageVariables that represent the constituent
        # elements, that way `_make_param` can handle the merging for us!
        return variables

    def get_metadata_column(self, name, column_name, variable):
        _ = super().get_metadata_column(name, column_name, variable)

        # build tmp var to use to_interface_name()
        tmp_var = self.variable_factory(column_name, lambda: None, 'column')

        def f():
            return (variable.to_interface_name(), tmp_var.to_interface_name())

        variable_new = self.variable_factory(name, f, 'column')
        return variable_new

    def action(self, action, inputs, outputs):
        variables = super().action(action, inputs, outputs)

        plugin_name = util.to_cli_name(action.plugin_id)
        action_name = util.to_cli_name(action.action_id)
        self.lines.append("qiime %s %s \\" % (plugin_name, action_name))

        action_f = action.get_action()
        action_state = get_action_state(action_f)

        output_vals = {v.name: v for v in variables}
        input_signature, output_signature = dict(), dict()
        for sig in action_state['signature']:
            if sig['type'] == 'output':
                output_signature[sig['name']] = sig
            else:
                input_signature[sig['name']] = sig

        self._write_param(input_signature, inputs)
        self._write_param(output_signature, outputs, output_vals=output_vals)
        self.lines[-1] = self.lines[-1][:-2]  # remove trailing \

        return variables

    def _write_param(self, signature, params, output_vals=None):
        for param_name, value in params.values.items():
            param_state = signature[param_name]
            if output_vals is not None:
                value = output_vals[value]
            if value is not None:
                for opt, val in self._make_param(value, param_state):
                    line = self.INDENT + opt
                    if val is not None:
                        line += ' ' + val
                    line += ' \\'

                    self.lines.append(line)

    def _make_param(self, value, state):
        state = state.copy()
        type_ = state.pop('type')

        opt = q2cli.click.option.GeneratedOption(prefix=type_[0], **state)
        option = opt.opts[0]

        # INPUTS AND OUTPUTS
        if type_ in ('input', 'output'):
            if isinstance(value, CLIUsageVariable):
                return [(option, value.to_interface_name())]
            else:
                if isinstance(value, set):
                    value = sorted(value, key=lambda x: x.to_interface_name())
                value = [v.to_interface_name() for v in value]
                return [(option, ' '.join(value))]

        # METADATA FILE
        if state['metadata'] == 'file':
            if isinstance(value, CLIUsageVariable):
                return [(option, value.to_interface_name())]
            else:
                value = [v.to_interface_name() for v in value]
                return [(option, ' '.join(value))]

        # METADATA COLUMN
        if state['metadata'] == 'column':
            # md cols are special, we have pre-computed the interface-specific
            # names and stashed them in the factory, so run execute()
            # to get the values
            fn, col_name = value.execute()
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
