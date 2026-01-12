from setuptools import setup, find_packages

setup(
    name="naoqi_proxy",
    version="0.1.0",
    packages=find_packages(),
    py_modules=["naoqi_proxy"],
    install_requires=[
        "requests"
    ],
    description="Python 3 bridge client for Naoqi",
)
