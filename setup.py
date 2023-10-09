# ----------------------------------------------------------------------------
# Copyright (c) 2016-2023, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

from setuptools import setup, find_packages
import versioneer

setup(
    name='q2cli',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    license='BSD-3-Clause',
    url='https://qiime2.org',
    packages=find_packages(),
    include_package_data=True,
    scripts=['bin/tab-qiime'],
    entry_points={
        'console_scripts': [
            'qiime=q2cli.__main__:qiime'
        ],
        'qiime2.usage_drivers': [
            'cli=q2cli.core.usage:ReplayCLIUsage'
        ]
    },
    package_data={
        'q2cli.tests': ['data/*'],
        'q2cli.core': ['assets/*']
    },
    zip_safe=False,
)
