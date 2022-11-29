from setuptools import setup

import docmaptools

with open("README.md") as fp:
    README = fp.read()

setup(
    name="docmaptools",
    version=docmaptools.__version__,
    description="Use DocMap content, generate JATS XML from it, and other utility functions.",
    long_description=README,
    long_description_content_type="text/markdown",
    packages=["docmaptools"],
    license="MIT",
    install_requires=[
        "elifetools",
        "requests",
    ],
    url="https://github.com/elifesciences/docmap-tools",
    maintainer="eLife Sciences Publications Ltd.",
    maintainer_email="tech-team@elifesciences.org",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.8",
    ],
)
