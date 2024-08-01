from setuptools import setup

setup(
    name="cordial-rt",
    version="0.1",
    author="Lasse Refsgaard",
    description="A collection of functions for organising and analysing radiotherapy DICOM files",
    packages=["cordial-rt"],
    package_dir={"coridalrt": "cordialrt"},
    author_email="LasseRefsgaard@gmail.com",
)
