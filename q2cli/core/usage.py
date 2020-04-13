# ----------------------------------------------------------------------------
# Copyright (c) 2016-2020, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

from qiime2.core.type.primitive import Bool

import qiime2.sdk.usage as usage
from qiime2 import Metadata, MetadataColumn
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

    def _init_data_(self, ref, factory):
        self._init_data_refs[ref] = factory
        data = factory()
        if isinstance(data, MetadataColumn):
            col = data.name
            md_file = ref  # Using ref just to make it easy atm
            return col, md_file
        return ref

    def _merge_metadata_(self, ref, records):
        merge_target = ref
        return merge_target

    def _get_metadata_column_(self, ref, record, column_name):
        md = record.result
        return column_name, md

    def _comment_(self, text: str):
        self._recorder.append('# %s' % (text,))

    def _action_(
        self, action: usage.UsageAction, input_opts: dict, output_opts: dict
    ):
        t = self._template_action(action, input_opts, output_opts)
        self._recorder.append(t)
        return output_opts

    def _assert_has_line_matching_(self, ref, label, path, expression):
        pass

    def render(self):
        return '\n'.join(self._recorder)

    def get_example_data(self):
        return {r: f() for r, f in self._init_data_refs.items()}

    def _extract_from_signature(self, action_sig):
        params, mds = [], []
        for i, spec in action_sig.parameters.items():
            q_type = spec.qiime_type
            if is_metadata_type(q_type):
                mds.append((i, spec))
            else:
                params.append((i, spec))
        return params, mds

    def _template_action(self, action, input_opts, outputs):
        action_f, action_sig = action.get_action()
        cmd = to_cli_name(f"qiime {action_f.plugin_id} {action_f.id}")
        params, mds = self._extract_from_signature(action_sig)
        inputs_t = self._template_inputs(action_sig, input_opts)
        params_t = self._template_parameters(params, input_opts)
        mds_t = self._template_metadata(mds, input_opts)
        outputs_t = self._template_outputs(action_sig, outputs)
        t = " \\\n".join([cmd] + inputs_t + params_t + mds_t + outputs_t)
        return t

    def _template_inputs(self, action_sig, input_opts):
        inputs = []
        for i in action_sig.inputs:
            if i in input_opts:
                p = f"--i-{to_cli_name(i)}"
                val = f"{input_opts[i]}.qza"
                inputs.append(f"{' ':>4}{p} {val}")
        return inputs

    def _template_parameters(self, params, input_opts):
        params_t = []
        for i, spec in params:
            val = str(input_opts[i]) if i in input_opts else ""
            if spec.qiime_type is Bool:
                pfx = f"--p-" if val == "True" else f"--p-no-"
                p = f"{pfx}{to_cli_name(i)}"
                params_t.append(f"{' ':>4}{p}")
            elif val:
                p = f"--p-{to_cli_name(i)}"
                _val = f" {val}"
                params_t.append(f"{' ':>4}{p + _val}")
        return params_t

    def _template_outputs(self, action_sig, outputs):
        outputs_t = []
        for i, spec in action_sig.outputs.items():
            qtype = spec.qiime_type
            ext = ".qzv" if is_visualization_type(qtype) else ".qza"
            p = f"--o-{to_cli_name(i)}"
            val = f"{to_snake_case(outputs[i])}{ext}"
            outputs_t.append(f"{' ':>4}{p} {val}")
        return outputs_t

    def _template_metadata(self, mds, input_opts):
        mds_t = []
        data = self.get_example_data()
        data = {k: v for k, v in data.items() if isinstance(v, Metadata)}
        file_param = f"--m-metadata-file"
        col_param = f"--m-metadata-column"
        for i, spec in mds:
            qtype = spec.qiime_type
            if not is_metadata_column_type(qtype):
                name = str(input_opts[i]) if i in input_opts else ""
                if name in data:
                    # Metadata item `i` was registered by Usage.init_data and
                    # can therefore be assumed *not* to be a merge target.
                    mds_t.append(f"{' ':>4}{file_param} {name}.tsv")
                else:
                    # Metadata item `i` was not registered by Usage.init_data
                    # and can therefore be assumed to be a merge target.
                    #
                    # Extract metadata that was merged into merge target `i`
                    for k, v in data.items():
                        mds_t.append(f"{' ':>4}{file_param} {k}.tsv")
            elif is_metadata_column_type(qtype):
                col, md = input_opts[i]
                mds_t.append(f"{' ':>4}{file_param} {md}.tsv")
                mds_t.append(f"{' ':>4}{col_param} '{col}'")
        return mds_t


def examples(action):
    all_examples = []
    for i in action.examples:
        use = CLIUsage()
        action.examples[i](use)
        example = use.render()
        comment = f"# {i}".replace('_', ' ')
        all_examples.append(comment)
        all_examples.append(f"{example}\n")
    return "\n\n".join(all_examples)
