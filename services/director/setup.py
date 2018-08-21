from setuptools import find_packages, setup


INSTALL_REQUIRES = [
'docker==3.5.0',
'Flask==1.0.1',
'tenacity==4.12.0',
'aiohttp_apiset==0.9.3',
'requests',
]

setup(
    name='director-service',
    version="0.1",
    description='Demos API',
    platforms=['POSIX'],
    package_dir={'': 'src'},
    packages=find_packages('src'),
    package_data={
        '': ['.openapi/swagger.yaml']
    },
    entry_points={
        'console_scripts': ['director-service=director.__main__:main']},
    include_package_data=True,
    install_requires=INSTALL_REQUIRES,
    zip_safe=False,
)
