# ----------------------------------------------------------------------------
# Copyright (c) 2016--, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------

from setuptools import setup, find_packages

setup(
    name='q2cli',
    version='0.0.0-dev',
    packages=find_packages(),
    include_package_data=True,
    install_requires=['click', 'qiime >= 2.0.0'],
    entry_points='''
        [console_scripts]
        qiime=q2cli.cli:main
    ''',
)
