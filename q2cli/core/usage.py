# ----------------------------------------------------------------------------
# Copyright (c) 2016-2020, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import collections
import textwrap

from qiime2.sdk import usage, util
from qiime2.sdk.util import (
    is_metadata_type,
    is_visualization_type,
)

from q2cli.util import to_cli_name


def is_iterable(val):
    return isinstance(val, collections.abc.Iterable)


class CLIUsage(usage.Usage):
    def __init__(self):
        super().__init__()
        self._cache_recorder = []
        self._init_data_refs = dict()

    def _add_cache_record(self, source, value):
        record = dict(source=source, value=value)
        self._cache_recorder.append(record)

    def _init_data_(self, ref, factory):
        self._init_data_refs[ref] = factory
        return ref

    def _init_metadata_(self, ref, factory):
        self._init_data_refs[ref] = factory
        return ref

    def _init_data_collection_(self, ref, collection_type, *records):
        return sorted([r.ref for r in records])

    def _merge_metadata_(self, ref, records):
        return sorted([r.ref for r in records])

    def _get_metadata_column_(self, column_name, record):
        return (record.ref, column_name)

    def _comment_(self, text):
        self._add_cache_record(source='comment', value=text)

    def _action_(self, action, input_opts, output_opts):
        action_f, action_sig = action.get_action()
        signature = self._destructure_signature(action_sig)
        inputs, params, mds, outputs = self._destructure_opts(
            signature, input_opts, output_opts)

        value = dict(plugin_id=action_f.plugin_id, action_id=action_f.id,
                     inputs=inputs, params=params, mds=mds, outputs=outputs)
        self._add_cache_record(source='action', value=value)
        return output_opts

    def _assert_has_line_matching_(self, ref, label, path, expression):
        pass

    def cache(self):
        return self._cache_recorder

    def get_example_data(self):
        return {r: f() for r, f in self._init_data_refs.items()}

    def _destructure_signature(self, action_sig):
        # In the future this should return a more robust spec subset
        def distill_spec(spec):
            return str(spec.qiime_type)

        inputs = {k: distill_spec(v) for k, v in action_sig.inputs.items()}
        outputs = {k: distill_spec(v) for k, v in action_sig.outputs.items()}
        params, mds = {}, {}

        for param_name, spec in action_sig.inputs.items():
            inputs[param_name] = distill_spec(spec)

        for param_name, spec in action_sig.parameters.items():
            if is_metadata_type(spec.qiime_type):
                mds[param_name] = distill_spec(spec)
            else:
                params[param_name] = distill_spec(spec)

        return {'inputs': inputs, 'params': params,
                'mds': mds, 'outputs': outputs}

    def _destructure_opts(self, signature, input_opts, output_opts):
        inputs, params, mds, outputs = {}, {}, {}, {}

        for opt_name, val in input_opts.items():
            if opt_name in signature['inputs'].keys():
                inputs[opt_name] = (val, signature['inputs'][opt_name])
            elif opt_name in signature['params'].keys():
                if is_iterable(val):
                    val = list(val)
                params[opt_name] = (val, signature['params'][opt_name])
            elif opt_name in signature['mds'].keys():
                mds[opt_name] = (val, signature['mds'][opt_name])

        for opt_name, val in output_opts.items():
            outputs[opt_name] = (val, signature['outputs'][opt_name])

        return inputs, params, mds, outputs


class CLIRenderer:
    def __init__(self, records):
        self.cache_records = records

    def render(self):
        if len(self.cache_records) == 0:
            yield 'No examples have been registered for this action yet.'
        else:
            for record in self.cache_records:
                yield self.dispatch(record)

    def dispatch(self, record):
        source = record['source']

        if source == 'comment':
            return self.template_comment(record['value'])
        elif source == 'action':
            return self.template_action(
                record['value']['plugin_id'],
                record['value']['action_id'],
                record['value']['inputs'],
                record['value']['params'],
                record['value']['mds'],
                record['value']['outputs'],
            )
        else:
            raise Exception('uh oh')

    def template_comment(self, comment):
        return f'# {comment}'

    def template_action(self, plugin_id, action_id,
                        inputs, params, mds, outputs):
        templates = [
            *self._template_inputs(inputs),
            *self._template_parameters(params),
            *self._template_metadata(mds),
            *self._template_outputs(outputs),
        ]

        base_cmd = to_cli_name(f'qiime {plugin_id} {action_id}')
        action_t = self._format_templates(base_cmd, templates)
        return action_t

    def _format_templates(self, command, templates):
        wrapper = textwrap.TextWrapper(initial_indent=' ' * 4)
        templates = [command] + [wrapper.fill(t) for t in templates]
        # TODO: double-check that string escaping is working
        return ' \\\n'.join(templates)

    def _template_inputs(self, input_opts):
        inputs = []
        for opt_name, (ref, _) in input_opts.items():
            refs = ref if isinstance(ref, list) else [ref]
            for ref in refs:
                opt_name = to_cli_name(opt_name)
                inputs.append(f'--i-{opt_name} {ref}.qza')
        return inputs

    def _template_parameters(self, param_opts):
        params = []
        for opt_name, (val, _) in param_opts.items():
            # TODO: circle back on sets
            # TODO: need to test parameter collections in test_usage.py
            vals = val if is_iterable(val) else [val]
            for val in sorted(vals):
                opt_name = to_cli_name(opt_name)
                params.append(f'--p-{opt_name} {val}')
        return params

    def _template_metadata(self, md_opts):
        mds = []
        for opt_name, (ref, _) in md_opts.items():
            ref = tuple(ref) if "Column" in _ else ref
            refs = ref if isinstance(ref, list) else [ref]
            for ref in refs:
                opt_name = to_cli_name(opt_name)
                col = None
                if isinstance(ref, tuple):
                    ref, col = ref
                mds.append(f'--m-{opt_name}-file {ref}.tsv')
                if col is not None:
                    mds.append(f'--m-{opt_name}-column \'{col}\'')
        return mds

    def _template_outputs(self, output_opts):
        outputs = []
        for opt_name, (ref, qiime_type) in output_opts.items():
            opt_name = to_cli_name(opt_name)
            qiime_type = util.parse_type(qiime_type)
            ext = 'qzv' if is_visualization_type(qiime_type) else 'qza'
            outputs.append(f'--o-{opt_name} {ref}.{ext}')
        return outputs


def cache_examples(action):
    all_examples = []
    for example in action.examples:
        use = CLIUsage()
        header = str(example).replace('_', ' ')
        use._comment_(f'### example: {header} ###')
        action.examples[example](use)
        cache = use.cache()
        all_examples.extend(cache)
    return all_examples


def examples(action):
    import q2cli.core.cache

    plugin_id = to_cli_name(action.plugin_id)
    cached_plugin = q2cli.core.cache.CACHE.plugins[plugin_id]
    cached_action = cached_plugin['actions'][action.id]
    cached_examples = cached_action['examples']

    cache_render = CLIRenderer(cached_examples)
    for rendered in cache_render.render():
        yield rendered
