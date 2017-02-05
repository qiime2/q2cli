# ----------------------------------------------------------------------------
# Copyright (c) 2016-2017, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

from setuptools import setup, find_packages

setup(
    name='q2cli',
    version='2017.2.0',
    license='BSD-3-Clause',
    url='https://qiime2.org',
    packages=find_packages(),
    include_package_data=True,
    install_requires=['click', 'qiime2 == 2017.2.*', 'pip'],
    scripts=['bin/tab-qiime'],
    entry_points='''
        [console_scripts]
        qiime=q2cli.__main__:qiime
    ''',
)
