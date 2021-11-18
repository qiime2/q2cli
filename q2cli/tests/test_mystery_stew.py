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

from q2cli.core.usage import CLIUsage
from q2cli.util import get_plugin_manager

import pytest


def _labeler(val):
    if hasattr(val, 'id'):
        return val.id
    return val


def get_tests():
    tests = []
    pm = get_plugin_manager()
    try:
        plugin = pm.plugins['mystery-stew']
    except KeyError:
        return tests
    for action in plugin.actions.values():
        for name in action.examples:
            tests.append((action, name))
    return tests


@pytest.mark.parametrize('action,example', get_tests(), ids=_labeler)
def test_mystery_stew(action, example):
    example_f = action.examples[example]
    use = CLIUsage(enable_assertions=True)
    example_f(use)
    rendered = '\n'.join(use.recorder)
    with tempfile.TemporaryDirectory() as tmpdir:
        for ref, data in use.get_example_data():
            data.save(os.path.join(tmpdir, ref))
        subprocess.run([rendered],
                       shell=True,
                       check=True,
                       cwd=tmpdir,
                       env={**os.environ})
