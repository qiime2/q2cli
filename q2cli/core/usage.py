# ----------------------------------------------------------------------------
# Copyright (c) 2016-2020, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

from qiime2.core.type.primitive import Bool

import qiime2.sdk.usage as usage
from qiime2.sdk.util import is_metadata_type

from q2cli.util import to_cli_name
from q2cli.util import to_snake_case


class CLIUsage(usage.Usage):
    def __init__(self):
        super().__init__()
        self._recorder = []
        self._init_data_refs = dict()
        self._metadata_refs = dict()
        self._col_refs = dict()

    def _init_data_(self, ref, factory):
        self._init_data_refs[ref] = factory
        # Don't need to compute anything, so just pass along the ref
        return ref

    def _merge_metadata_(self, ref, records):
        merge_target = ref
        for record in records:
            self._metadata_refs[record.ref] = record.result
        return merge_target

    def _get_metadata_column_(self, ref, record, column_name):
        self._metadata_refs[record.ref] = record.result
        self._col_refs[record.ref] = column_name
        return ref

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
        inputs, params, cli_outputs = [], [], []
        for i in action_f.signature.inputs:
            p = f"--i-{to_cli_name(i)}"
            val = f"{input_opts[i]}.qza"
            inputs.append(f"{' ':>4}{p} {val}")

        for i, spec in action_f.signature.parameters.items():
            if i in input_opts and not is_metadata_type(spec.qiime_type):
                p = f"--p-{to_cli_name(i)}"
                val = ""
                if spec.qiime_type is not Bool:
                    val = f" {input_opts[i]}"
                params.append(f"{' ':>4}{p + val}")

        for i in self._metadata_refs:
            p = f"--m-metadata-file"
            val = f"{i}.tsv"
            params.append(f"{' ':>4}{p} {val}")
            try:
                col = self._col_refs[i]
                p = f"--m-metadata-column"
                params.append(f"{' ':>4}{p} {col}")
            except KeyError:
                pass

        for i in action_f.signature.outputs:
            p = f"--o-{to_cli_name(i)}"
            val = f"{to_snake_case(outputs[i])}.qza"
            cli_outputs.append(f"{' ':>4}{p} {val}")

        t = " \\\n".join([cmd] + inputs + params + cli_outputs)
        return t
