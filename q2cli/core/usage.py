# ----------------------------------------------------------------------------
# Copyright (c) 2016-2020, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------
import textwrap
import itertools

from qiime2.core.type.primitive import Bool

import qiime2.sdk.usage as usage
from qiime2.sdk.util import (
    is_metadata_type,
    is_visualization_type,
    is_metadata_column_type,
    is_collection_type
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
        return ref

    def _init_metadata_(self, ref, factory):
        self._init_data_refs[ref] = factory
        return ref

    def _merge_metadata_(self, ref, records):
        mergees = [i.ref for i in records]
        return ref, mergees

    def _get_metadata_column_(self, column_name, record):
        return record.ref, column_name

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
        templates = [inputs_t, params_t, mds_t, outputs_t]
        action_t = self._format_templates(cmd, templates)
        return action_t

    def _format_templates(self, command, templates):
        wrapper = textwrap.TextWrapper(initial_indent=" " * 4)
        templates = itertools.chain(*templates)
        templates = map(wrapper.fill, templates)
        action_t = [command] + list(templates)
        action_t = " \\\n".join(action_t)
        return action_t

    def _template_inputs(self, action_sig, input_opts):
        inputs = []
        for i in action_sig.inputs:
            if i in input_opts:
                p = f"--i-{to_cli_name(i)}"
                val = f"{input_opts[i]}.qza"
                inputs.append(f"{p} {val}")
        return inputs

    def _template_parameters(self, params, input_opts):
        params_t = []
        for i, spec in params:
            val = str(input_opts[i]) if i in input_opts else ""
            if spec.qiime_type is Bool:
                pfx = "--p-" if val == "True" else "--p-no-"
                p = f"{pfx}{to_cli_name(i)}"
                params_t.append(p)
            elif val:
                p = f"--p-{to_cli_name(i)}"
                _val = f" {val}"
                params_t.append(f"{p + _val}")
        return params_t

    def _template_outputs(self, action_sig, outputs):
        outputs_t = []
        for i, spec in action_sig.outputs.items():
            qtype = spec.qiime_type
            ext = ".qzv" if is_visualization_type(qtype) else ".qza"
            p = f"--o-{to_cli_name(i)}"
            val = f"{to_snake_case(outputs[i])}{ext}"
            outputs_t.append(f"{p} {val}")
        return outputs_t

    def _template_metadata(self, mds, input_opts):
        mds_t = []
        file_param = "--m-metadata-file"
        col_param = "--m-metadata-column"
        for i, spec in mds:
            name = input_opts[i]
            if not isinstance(name, str):
                name, result = name
            record = self._get_record(name)
            source = record.source
            if source == "init_metadata":
                mds_t.append(f"{file_param} {name}.tsv")
                if is_metadata_column_type(spec.qiime_type):
                    mds_t.append(f"{col_param} '{result}'")
            elif source == "merge_metadata":
                # Extract implicitly merged metadata params
                for mergee in result:
                    mds_t.append(f"{file_param} {mergee}.tsv")
            elif source == "get_metadata_column":
                ref, result = record.result
                md, col = result
                mds_t.append(f"{file_param} {md}.tsv")
                mds_t.append(f"{col_param} '{col}'")
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
