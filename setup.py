#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='andi',
    version='0.6.0',
    description='Library for annotation-based dependency injection',
    long_description=open('README.rst').read() + "\n\n" + open('CHANGES.rst').read(),
    long_description_content_type='text/x-rst',
    author='Mikhail Korobov',
    author_email='kmike84@gmail.com',
    url='https://github.com/scrapinghub/andi',
    packages=find_packages(exclude=['tests']),
    package_data={"andi": ["py.typed"]},
    zip_safe=False,
    python_requires='>=3.8.1',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
)
