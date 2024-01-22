# ----------------------------------------------------------------------------
# Copyright (c) 2016-2023, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------


def get_plugin_state(plugin):
    state = {
        # TODO this conversion also happens in the framework
        # (qiime2/plugins.py) to generate an importable module name from a
        # plugin's `.name` attribute. Centralize this knowledge in the
        # framework, ideally as a machine-friendly plugin ID (similar to
        # `Action.id`).
        'id': plugin.name.replace('-', '_'),
        'name': plugin.name,
        'version': plugin.version,
        'website': plugin.website,
        'user_support_text': plugin.user_support_text,
        'description': plugin.description,
        'short_description': plugin.short_description,
        'actions': {}
    }

    for id, action in plugin.actions.items():
        state['actions'][id] = get_action_state(action)

    return state


def get_action_state(action):
    import itertools

    state = {
        'id': action.id,
        'name': action.name,
        'description': action.description,
        'signature': [],
        'epilog': [],
        'deprecated': action.deprecated,
    }

    sig = action.signature
    for name, spec in itertools.chain(sig.signature_order.items(),
                                      sig.outputs.items()):
        data = {'name': name, 'repr': _get_type_repr(spec.qiime_type),
                'ast': spec.qiime_type.to_ast()}

        if name in sig.inputs:
            type = 'input'
        elif name in sig.parameters:
            type = 'parameter'
        else:
            type = 'output'
        data['type'] = type

        if spec.has_description():
            data['description'] = spec.description
        if spec.has_default():
            data['default'] = spec.default

        data['metavar'] = _get_metavar(spec.qiime_type)
        data['multiple'], data['is_bool_flag'], data['metadata'] = \
            _special_option_flags(spec.qiime_type)

        state['signature'].append(data)

    return state


def _special_option_flags(type):
    import qiime2.sdk.util
    import itertools

    multiple = None
    is_bool_flag = False
    metadata = None

    style = qiime2.sdk.util.interrogate_collection_type(type)

    if style.style is not None:
        multiple = style.view.__name__
        if style.style == 'simple':
            names = {style.members.name, }
        elif style.style == 'complex':
            names = {m.name for m in
                     itertools.chain.from_iterable(style.members)}
        else:  # composite or monomorphic
            names = {v.name for v in style.members}

        if 'Bool' in names:
            is_bool_flag = True
    else:  # not collection
        expr = style.expr

        if expr.name == 'Metadata':
            multiple = 'list'
            metadata = 'file'
        elif expr.name == 'MetadataColumn':
            metadata = 'column'
        elif expr.name == 'Bool':
            is_bool_flag = True

    return multiple, is_bool_flag, metadata


def _get_type_repr(type):
    import qiime2.sdk.util

    type_repr = repr(type)
    style = qiime2.sdk.util.interrogate_collection_type(type)

    if not qiime2.sdk.util.is_semantic_type(type) and \
            not qiime2.sdk.util.is_union(type):
        if style.style is None:
            if style.expr.predicate is not None:
                type_repr = repr(style.expr.predicate)
            elif not type.fields:
                type_repr = None
        elif style.style == 'simple':
            if style.members.predicate is not None:
                type_repr = repr(style.members.predicate)

    return type_repr


def _get_metavar(type):
    import qiime2.sdk.util

    name_to_var = {
        'Visualization': 'VISUALIZATION',
        'Int': 'INTEGER',
        'Str': 'TEXT',
        'Float': 'NUMBER',
        'Bool': '',
        'Jobs': 'NJOBS',
        'Threads': 'NTHREADS',
    }

    style = qiime2.sdk.util.interrogate_collection_type(type)

    multiple = style.style is not None
    if style.style == 'simple':
        inner_type = style.members
    elif not multiple:
        inner_type = type
    else:
        inner_type = None

    if qiime2.sdk.util.is_semantic_type(type):
        metavar = 'ARTIFACT'
    elif qiime2.sdk.util.is_metadata_type(type):
        metavar = 'METADATA'
    elif style.style is not None and style.style != 'simple':
        metavar = 'VALUE'
    elif qiime2.sdk.util.is_union(type):
        metavar = 'VALUE'
    else:
        metavar = name_to_var[inner_type.name]
    if (metavar == 'NUMBER' and inner_type is not None
            and inner_type.predicate is not None
            and inner_type.predicate.template.start == 0
            and inner_type.predicate.template.end == 1):
        metavar = 'PROPORTION'

    if multiple or type.name == 'Metadata':
        if metavar != 'TEXT' and metavar != '' and metavar != 'METADATA':
            metavar += 'S'
        metavar += '...'

    return metavar
