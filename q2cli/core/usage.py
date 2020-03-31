# ----------------------------------------------------------------------------
# Copyright (c) 2016-2020, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import qiime2.sdk.usage as usage


class CLIUsage(usage.Usage):
    def __init__(self):
        super().__init__()
        self._recorder = []
        self._init_data_refs = dict()
        self._metadata_refs = dict()

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
        t = '%s = %s.get_column(%r)\n' % (ref, record.ref, column_name)
        self._recorder.append(t)
        return ref

    def _comment_(self, text: str):
        self._recorder.append('# %s' % (text,))

    def _action_(
        self, action: usage.UsageAction, input_opts: dict, output_opts: dict
    ):
        action_f, action_sig = action.get_action()
        t = self._template_action(action_f, input_opts, output_opts)
        self._recorder.append(t)

        new_output_opts = {k: k for k in output_opts.keys()}
        return new_output_opts

    def _assert_has_line_matching_(self, ref, label, path, expression):
        pass

    def render(self):
        return '\n'.join(self._recorder)

    def get_example_data(self):
        return {r: f() for r, f in self._init_data_refs.items()}

    def _template_action(self, action_f, input_opts, outputs):
        # The following assumes a 1-1 relationship between params and targets
        cmd = f"qiime {action_f.plugin_id} {action_f.id}".replace("_", "-")
        inputs = [
            f"{' ':>4}--i-{i.replace('_', '-')} {input_opts[i]}.qza"
            for i in action_f.signature.inputs
        ]

        params = []
        for i in action_f.signature.parameters:
            if i in input_opts and i != "metadata":
                spec = action_f.signature.parameters[i]
                p = f"--p-{i.replace('_', '-')}"
                val = input_opts[i]
                val = f" {val}" if not isinstance(val, bool) else ""
                params.append(f"{' ':>4}{p}{val}")
        for i in self._metadata_refs:
            p = f"--m-metadata-file"
            val = f"{i}.tsv"
            params.append(f"{' ':>4}{p} {val}")

        # HACK: Reverse output dict for now
        rev_outputs = {v: k for k, v in outputs.items()}
        cli_outputs = [
            (
                f"{' ':>4}--o-{i.replace('_', '-')} "
                f"{rev_outputs[i].replace('-', '_')}.qza"
            )
            for i in action_f.signature.outputs
        ]
        t = " \\\n".join([cmd] + inputs + params + cli_outputs)
        return t
