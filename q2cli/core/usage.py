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
        self._imports = set()
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

    def _action_(self, action: usage.UsageAction, input_opts: dict, output_opts: dict):
        action_f, action_sig = action.get_action()
        # TODO: Probably don't need this
        self._update_imports(action_f)
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
        # Might be able to use just one list
        inputs, params = [], []
        for k, v in input_opts.items():
            if v in self._scope.records:
                inputs.append(f"{' ':>4}--i-{k} {v}.qza")
            else:
                params.append(f"{' ':>4}--p-{k} {v}")

        cli_outputs = []
        for k, v in outputs.items():
            param = f"{' ':>4}--o-{v}".replace("_", "-")
            target = f"{k}.qza"
            cli_outputs.append(f"{param} {target}")
        t = " \\\n".join([cmd] + inputs + params + cli_outputs)
        return t

    def _update_imports(self, action_f):
        # TODO:  Probably don't care about imports for this driver
        full_import = action_f.get_import_path()
        import_path, action_api_name = full_import.rsplit('.', 1)
        self._imports.add((import_path, action_api_name))
