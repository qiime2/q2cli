# ----------------------------------------------------------------------------
# Copyright (c) 2016-2020, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import pytest

from q2cli.core.usage import CLIUsage
from qiime2.core.testing.util import get_dummy_plugin


params = [
    (
        'concatenate_ints',
        'concatenate_ints_simple',
        (
            "# This example demonstrates basic usage.",
            "qiime dummy-plugin concatenate-ints \\",
            "    --i-ints1 ints_a.qza \\",
            "    --i-ints2 ints_b.qza \\",
            "    --i-ints3 ints_c.qza \\",
            "    --p-int1 4 \\",
            "    --p-int2 2 \\",
            "    --o-concatenated-ints ints_d.qza",
        ),
    ),
    (
        'concatenate_ints',
        'concatenate_ints_complex',
        (
            "# This example demonstrates chained usage (pt 1).",
            "qiime dummy-plugin concatenate-ints \\",
            "    --i-ints1 ints_a.qza \\",
            "    --i-ints2 ints_b.qza \\",
            "    --i-ints3 ints_c.qza \\",
            "    --p-int1 4 \\",
            "    --p-int2 2 \\",
            "    --o-concatenated-ints ints_d.qza",
            # TODO: Test to make sure there is additional \n here?
            "# This example demonstrates chained usage (pt 2).",
            "qiime dummy-plugin concatenate-ints \\",
            "    --i-ints1 ints_d.qza \\",
            "    --i-ints2 ints_b.qza \\",
            "    --i-ints3 ints_c.qza \\",
            "    --p-int1 41 \\",
            "    --p-int2 0 \\",
            "    --o-concatenated-ints concatenated_ints.qza",
        ),
    ),
    (
        'typical_pipeline',
        'typical_pipeline_simple',
        (
            "qiime dummy-plugin typical-pipeline \\",
            "    --i-int-sequence ints.qza \\",
            "    --i-mapping mapper.qza \\",
            "    --p-do-extra-thing \\",
            "    --o-out-map out_map.qza \\",
            "    --o-left left.qza \\",
            "    --o-right right.qza \\",
            "    --o-left-viz left_viz.qza \\",
            "    --o-right-viz right_viz.qza"
        ),
    ),
]


@pytest.fixture
def dummy_plugin():
    return get_dummy_plugin()


@pytest.mark.parametrize("action, example, exp", params)
def test_render(dummy_plugin, action, example, exp):
    action = dummy_plugin.actions[action]
    use = CLIUsage()
    action.examples[example](use)
    assert "\n".join(exp) == use.render()
