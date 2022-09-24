from setuptools import setup

setup(
    name='aggregates',
    version='0.0.0',
    package_dir={'': 'src'},
    packages=['project_management'],
    py_modules=['app', 'aggregate_root'],
    requires=[
        'python-event-sourcery>=0.1.7',
        'sqlalchemy,'
    ]
)
