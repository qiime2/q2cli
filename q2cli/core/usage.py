# ----------------------------------------------------------------------------
# Copyright (c) 2016-2020, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

from qiime2.core.type.primitive import Bool

import qiime2.sdk.usage as usage
from qiime2.sdk.util import (
    is_metadata_type,
    is_metadata_column_type,
    is_visualization_type,
)

from q2cli.util import to_cli_name
from q2cli.util import to_snake_case


class CLIUsage(usage.Usage):
    def __init__(self):
        super().__init__()
        self._recorder = []
        self._init_data_refs = dict()
        self._metadata_refs = dict()
        self._col_refs = dict()
        self._merge_targets = []

    def _init_data_(self, ref, factory):
        self._init_data_refs[ref] = factory
        # Don't need to compute anything, so just pass along the ref
        return ref

    def _merge_metadata_(self, ref, records):
        merge_target = ref
        self._merge_targets.append(merge_target)
        for record in records:
            self._metadata_refs[record.ref] = record.result
        return merge_target

    def _get_metadata_column_(self, ref, record, column_name):
        self._metadata_refs[record.ref] = record.result
        self._col_refs[record.ref] = column_name
        return record.result

    def _comment_(self, text: str):
        self._recorder.append('# %s' % (text,))

    def _action_(
        self, action: usage.UsageAction, input_opts: dict, output_opts: dict
    ):
        action_f, action_sig = action.get_action()
        t = self._template_action(action_f, input_opts, output_opts)
        self._recorder.append(t)
        return output_opts

    def _assert_has_line_matching_(self, ref, label, path, expression):
        pass

    def render(self):
        return '\n'.join(self._recorder)

    def get_example_data(self):
        return {r: f() for r, f in self._init_data_refs.items()}

    def _template_action(self, action_f, input_opts, outputs):
        cmd = to_cli_name(f"qiime {action_f.plugin_id} {action_f.id}")
        inputs = template_inputs(action_f, input_opts)
        params = self.template_parameters(action_f, input_opts)
        params += self.template_metadata()
        cli_outputs = template_outputs(action_f, outputs)
        t = " \\\n".join([cmd] + inputs + params + cli_outputs)
        return t

    def template_parameters(self, action_f, input_opts):
        params = []
        for i, spec in action_f.signature.parameters.items():
            qtype = spec.qiime_type
            val = str(input_opts[i]) if i in input_opts else ""
            if spec.qiime_type is Bool:
                pfx = f"--p-" if val == "True" else f"--p-no-"
                p = f"{pfx}{to_cli_name(i)}"
                params.append(f"{' ':>4}{p}")
            elif not is_metadata_type(qtype) and val:
                p = f"--p-{to_cli_name(i)}"
                _val = f" {val}"
                params.append(f"{' ':>4}{p + _val}")
            elif is_metadata_type(qtype) and val not in self._merge_targets:
                if is_metadata_column_type(qtype) and val not in self._col_refs:
                    self._col_refs[val] = val
                else:
                    self._metadata_refs[val] = val
        return params

    def template_metadata(self):
        params = []
        for i in self._metadata_refs:
            p = f"--m-metadata-file"
            val = f"{i}.tsv"
            params.append(f"{' ':>4}{p} {val}")
        for i in self._col_refs:
            if i not in self._metadata_refs:
                p = f"--m-metadata-file"
                val = f"{i}.tsv"
                params.append(f"{' ':>4}{p} {val}")
            col = self._col_refs[i]
            p = f"--m-metadata-column"
            params.append(f"{' ':>4}{p} '{col}'")
        return params


def template_inputs(action, input_opts):
    inputs = []
    for i in action.signature.inputs:
        p = f"--i-{to_cli_name(i)}"
        val = f"{input_opts[i]}.qza"
        inputs.append(f"{' ':>4}{p} {val}")
    return inputs


def template_outputs(action, outputs):
    cli_outputs = []
    for i, spec in action.signature.outputs.items():
        qtype = spec.qiime_type
        ext = ".qzv" if is_visualization_type(qtype) else ".qza"
        p = f"--o-{to_cli_name(i)}"
        val = f"{to_snake_case(outputs[i])}{ext}"
        cli_outputs.append(f"{' ':>4}{p} {val}")
    return cli_outputs
