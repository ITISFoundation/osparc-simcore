from setuptools import find_packages, setup


INSTALL_REQUIRES = [
'docker==3.5.0',
'tenacity==4.12.0',
'aiohttp==3.3.2',
'aiohttp_apiset==0.9.3',
'requests==2.19.1',
]

setup(
    name='simcore-director-webserver',
    version="0.1.0",
    description='oSparc Director webserver service',
    platforms=['POSIX'],
    package_dir={'': 'src'},
    packages=find_packages('src'),
    package_data={
        '': ['.openapi/v1/*']
    },
    entry_points={
        'console_scripts': ['simcore-director-webserver=director.__main__:main']},
    include_package_data=True,
    install_requires=INSTALL_REQUIRES,
    zip_safe=False,    
)
