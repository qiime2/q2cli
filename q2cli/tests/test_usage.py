# ----------------------------------------------------------------------------
# Copyright (c) 2016-2021, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import pytest

from q2cli.core.usage import examples

from qiime2.core.testing.util import get_dummy_plugin


@pytest.fixture
def dummy_plugin(monkeypatch):
    monkeypatch.setenv('QIIMETEST', '')
    return get_dummy_plugin()


params = [
    (
        'concatenate_ints',
        """\
# ### example: concatenate ints simple ###
# This example demonstrates basic usage.
qiime dummy-plugin concatenate-ints \\
    --i-ints1 ints_a.qza \\
    --i-ints2 ints_b.qza \\
    --i-ints3 ints_c.qza \\
    --p-int1 4 \\
    --p-int2 2 \\
    --o-concatenated-ints ints_d.qza
# ### example: concatenate ints complex ###
# This example demonstrates chained usage (pt 1).
qiime dummy-plugin concatenate-ints \\
    --i-ints1 ints_a.qza \\
    --i-ints2 ints_b.qza \\
    --i-ints3 ints_c.qza \\
    --p-int1 4 \\
    --p-int2 2 \\
    --o-concatenated-ints ints_d.qza
# This example demonstrates chained usage (pt 2).
qiime dummy-plugin concatenate-ints \\
    --i-ints1 ints_d.qza \\
    --i-ints2 ints_b.qza \\
    --i-ints3 ints_c.qza \\
    --p-int1 41 \\
    --p-int2 0 \\
    --o-concatenated-ints concatenated_ints.qza
# ### example: comments only ###
# comment 1
# comment 2""",
    ),
    (
        'identity_with_metadata',
        """\
# ### example: identity with metadata simple ###
qiime dummy-plugin identity-with-metadata \\
    --i-ints ints.qza \\
    --m-metadata-file md.tsv \\
    --o-out out.qza
# ### example: identity with metadata merging ###
qiime dummy-plugin identity-with-metadata \\
    --i-ints ints.qza \\
    --m-metadata-file md1.tsv \\
    --m-metadata-file md2.tsv \\
    --o-out out.qza""",
    ),
    (
        'identity_with_metadata_column',
        """\
# ### example: identity with metadata column get mdc ###
qiime dummy-plugin identity-with-metadata-column \\
    --i-ints ints.qza \\
    --m-metadata-file md.tsv \\
    --m-metadata-column 'a' \\
    --o-out out.qza""",
    ),
    (
        'typical_pipeline',
        """\
# ### example: typical pipeline simple ###
qiime dummy-plugin typical-pipeline \\
    --i-int-sequence ints.qza \\
    --i-mapping mapper.qza \\
    --p-do-extra-thing True \\
    --o-out-map out_map.qza \\
    --o-left left.qza \\
    --o-right right.qza \\
    --o-left-viz left_viz.qzv \\
    --o-right-viz right_viz.qzv
# ### example: typical pipeline complex ###
qiime dummy-plugin typical-pipeline \\
    --i-int-sequence ints1.qza \\
    --i-mapping mapper1.qza \\
    --p-do-extra-thing True \\
    --o-out-map out_map1.qza \\
    --o-left left1.qza \\
    --o-right right1.qza \\
    --o-left-viz left_viz1.qzv \\
    --o-right-viz right_viz1.qzv
qiime dummy-plugin typical-pipeline \\
    --i-int-sequence left1.qza \\
    --i-mapping out_map1.qza \\
    --p-do-extra-thing False \\
    --o-out-map out_map2.qza \\
    --o-left left2.qza \\
    --o-right right2.qza \\
    --o-left-viz left_viz2.qzv \\
    --o-right-viz right_viz2.qzv""",
    ),
    (
        'optional_artifacts_method',
        """\
# ### example: optional inputs ###
qiime dummy-plugin optional-artifacts-method \\
    --i-ints ints.qza \\
    --p-num1 1 \\
    --o-output output.qza
qiime dummy-plugin optional-artifacts-method \\
    --i-ints ints.qza \\
    --p-num1 1 \\
    --p-num2 2 \\
    --o-output output.qza
qiime dummy-plugin optional-artifacts-method \\
    --i-ints ints.qza \\
    --p-num1 1 \\
    --p-num2 None \\
    --o-output ints_b.qza
qiime dummy-plugin optional-artifacts-method \\
    --i-ints ints.qza \\
    --i-optional1 ints_b.qza \\
    --p-num1 3 \\
    --p-num2 4 \\
    --o-output output.qza""",
    ),
    (
        'variadic_input_method',
        """\
# ### example: variadic input simple ###
qiime dummy-plugin variadic-input-method \\
    --i-ints ints_a.qza \\
    --i-ints ints_b.qza \\
    --i-int-set single_int1.qza \\
    --i-int-set single_int2.qza \\
    --p-nums 7 \\
    --p-nums 8 \\
    --p-nums 9 \\
    --o-output out.qza""",
    ),
]


@pytest.mark.parametrize('action, exp', params)
def test_examples(dummy_plugin, action, exp):
    action = dummy_plugin.actions[action]
    result = list(examples(action))
    assert exp == '\n'.join(result)
