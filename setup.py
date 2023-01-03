from setuptools import setup

setup(
    name='cordial-rt',
    version='0.1',
    author='Lasse Refsgaard',
    description= 'A collection of functions for organising and analysing radiotherapy DICOM files',
    packages=['cordial-rt'],
    package_dir={'coridal-rt': 'cordial-rt'},
    author_email='LasseRefsgaard@gmail.com',
)