# ----------------------------------------------------------------------------
# Copyright (c) 2016-2020, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

from qiime2.core.type.primitive import Bool
import qiime2.sdk.usage as usage


class CLIUsage(usage.Usage):
    def __init__(self):
        super().__init__()
        self._recorder = []
        self._init_data_refs = dict()

    def _init_data_(self, ref, factory):
        self._init_data_refs[ref] = factory
        # Don't need to compute anything, so just pass along the ref
        return ref

    def _merge_metadata_(self, ref, records):
        first_md = records[0].ref
        remaining_records = ', '.join([r.ref for r in records[1:]])
        t = '%s = %s.merge(%s)\n' % (ref, first_md, remaining_records)
        self._recorder.append(t)
        return ref

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
            spec = action_f.signature.parameters[i]
            if spec.qiime_type is Bool and i in input_opts:
                params.append(f"{' ':>4}--p-{i.replace('_', '-')}")
            elif i in input_opts:
                p = f"--p-{i.replace('_', '-')}"
                val = f" {input_opts[i]}"
                params.append(f"{' ':>4}{p}{val}")

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
