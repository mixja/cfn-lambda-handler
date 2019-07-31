#!/usr/bin/env python
# coding: utf-8

from setuptools import setup

setup(
    name='cfn_lambda_handler',
    version='1.3.0',
    packages=[ 'cfn_lambda_handler' ],
    install_requires=[ 'requests' ],
    provides=[ 'cfn_lambda_handler' ],
    author='Justin Menga',
    author_email='justin.menga@gmail.com',
    url='https://github.com/mixja/cfn-lambda-handler',
    description='This package provides a decorator for Python Lambda functions handling AWS CloudFormation custom resources.',
    keywords='lambda aws cloudformation',
    license='ISC',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'License :: OSI Approved :: ISC License (ISCL)',
    ],
)