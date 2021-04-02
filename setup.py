from setuptools import setup

setup(
    name='aggregates',
    version='0.0.0',
    tests_require=['pytest'],
    package_dir={'': 'src'},
    packages=['project_management'],
    py_modules=['app', 'aggregate_root'],
)
