from setuptools import setup, find_packages

setup(
    name="pytest-simcore",
    version="0.1.0",
    maintainer="pcrespov, sanderegg",
    description="pytest plugin with fixtures and test helpers for osparc-simcore repo modules",
    py_modules=["pytest_simcore"],
    python_requires=">=3.6.*",
    # TODO create partial extensions:
    install_requires=["pytest>=3.5.0"],
    extras_require={
        "all": [
            "aio-pika",
            "aiohttp",
            "aioredis",
            "celery",
            "docker",
            "python-socketio",
            "PyYAML",
            "sqlalchemy[postgresql_psycopg2binary]",
            "tenacity",
            "yarl",
        ],
    },
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Framework :: Pytest",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: MIT License",
    ],
    entry_points={"pytest11": ["simcore = pytest_simcore"]},
)
