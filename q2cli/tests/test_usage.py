# ----------------------------------------------------------------------------
# Copyright (c) 2016-2021, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import os
import subprocess
import tempfile

from q2cli.core.usage import CLIUsageFormatter

from qiime2.core.testing.util import get_dummy_plugin
import pytest


def _rt_labeler(val):
    if hasattr(val, 'id'):
        return val.id
    return val


@pytest.fixture
def dummy_plugin(monkeypatch):
    monkeypatch.setenv('QIIMETEST', '')
    return get_dummy_plugin()


def get_templated_tests():
    return [
        ('concatenate_ints',
         """\
# This example demonstrates basic usage.
qiime dummy-plugin concatenate-ints \\
  --i-ints1 ints-a.qza \\
  --i-ints2 ints-b.qza \\
  --i-ints3 ints-c.qza \\
  --p-int1 4 \\
  --p-int2 2 \\
  --o-concatenated-ints ints-d.qza
# This example demonstrates chained usage (pt 1).
qiime dummy-plugin concatenate-ints \\
  --i-ints1 ints-a.qza \\
  --i-ints2 ints-b.qza \\
  --i-ints3 ints-c.qza \\
  --p-int1 4 \\
  --p-int2 2 \\
  --o-concatenated-ints ints-d.qza
# This example demonstrates chained usage (pt 2).
qiime dummy-plugin concatenate-ints \\
  --i-ints1 ints-d.qza \\
  --i-ints2 ints-b.qza \\
  --i-ints3 ints-c.qza \\
  --p-int1 41 \\
  --p-int2 0 \\
  --o-concatenated-ints concatenated-ints.qza
# comment 1
# comment 2
# comment 1
# comment 2"""),
        ('identity_with_metadata',
         """\
qiime dummy-plugin identity-with-metadata \\
  --i-ints ints.qza \\
  --m-metadata-file md.tsv \\
  --o-out out.qza
qiime dummy-plugin identity-with-metadata \\
  --i-ints ints.qza \\
  --m-metadata-file md1.tsv md2.tsv \\
  --o-out out.qza"""),
        ('identity_with_metadata_column',
         """\
qiime dummy-plugin identity-with-metadata-column \\
  --i-ints ints.qza \\
  --m-metadata-file md.tsv \\
  --m-metadata-column a \\
  --o-out out.qza"""),
        ('typical_pipeline',
         """\
qiime dummy-plugin typical-pipeline \\
  --i-int-sequence ints.qza \\
  --i-mapping mapper.qza \\
  --p-do-extra-thing \\
  --o-out-map out-map.qza \\
  --o-left left.qza \\
  --o-right right.qza \\
  --o-left-viz left-viz.qzv \\
  --o-right-viz right-viz.qzv
qiime dummy-plugin typical-pipeline \\
  --i-int-sequence ints1.qza \\
  --i-mapping mapper1.qza \\
  --p-do-extra-thing \\
  --o-out-map out-map1.qza \\
  --o-left left1.qza \\
  --o-right right1.qza \\
  --o-left-viz left-viz1.qzv \\
  --o-right-viz right-viz1.qzv
qiime dummy-plugin typical-pipeline \\
  --i-int-sequence left1.qza \\
  --i-mapping out-map1.qza \\
  --p-no-do-extra-thing \\
  --o-out-map out-map2.qza \\
  --o-left left2.qza \\
  --o-right right2.qza \\
  --o-left-viz left-viz2.qzv \\
  --o-right-viz right-viz2.qzv
qiime dev assert-result-data right2.qza --zip-data-path ints.txt --expression 1
qiime dev assert-result-type right2.qza --qiime-type IntSequence1
qiime dev assert-result-type out-map1.qza --qiime-type Mapping"""),  # noqa: 501
        ('optional_artifacts_method',
         """\
qiime dummy-plugin optional-artifacts-method \\
  --i-ints ints.qza \\
  --p-num1 1 \\
  --o-output output1.qza
qiime dummy-plugin optional-artifacts-method \\
  --i-ints ints.qza \\
  --p-num1 1 \\
  --p-num2 2 \\
  --o-output output2.qza
qiime dummy-plugin optional-artifacts-method \\
  --i-ints ints.qza \\
  --p-num1 1 \\
  --o-output output3.qza
qiime dummy-plugin optional-artifacts-method \\
  --i-ints ints.qza \\
  --i-optional1 output3.qza \\
  --p-num1 3 \\
  --p-num2 4 \\
  --o-output output4.qza"""),
        ('variadic_input_method',
         """\
qiime dummy-plugin variadic-input-method \\
  --i-ints ints-a.qza ints-b.qza \\
  --i-int-set single-int1.qza single-int2.qza \\
  --p-nums 7 8 9 \\
  --o-output out.qza"""),
        ]


_templ_ids = [x[0] for x in get_templated_tests()]


@pytest.mark.parametrize('action,exp', get_templated_tests(), ids=_templ_ids)
def test_templated(dummy_plugin, action, exp):
    action = dummy_plugin.actions[action]

    use = CLIUsageFormatter(enable_assertions=True)
    for example_f in action.examples.values():
        example_f(use)

    obs = use.render()
    assert exp == obs


def get_rt_tests():
    tests = []
    try:
        plugin = get_dummy_plugin()
    except RuntimeError:
        return tests

    for action in plugin.actions.values():
        for name in action.examples:
            tests.append((action, name))

    return tests


@pytest.mark.parametrize('action,example', get_rt_tests(), ids=_rt_labeler)
def test_round_trip(action, example):
    example_f = action.examples[example]
    use = CLIUsageFormatter(enable_assertions=True)
    example_f(use)
    rendered = use.render()
    with tempfile.TemporaryDirectory() as tmpdir:
        for ref, data in use.get_example_data():
            data.save(os.path.join(tmpdir, ref))
        subprocess.run([rendered],
                       shell=True,
                       check=True,
                       cwd=tmpdir,
                       env={**os.environ})
