#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Setup script for sendDetections package.
"""

import os
from setuptools import setup, find_packages

# Read the README.md for the long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Main setup configuration
setup(
    name="sendDetections",
    version="0.1.0",
    description="CSV to Recorded Future Detection API submission utility",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    license="MIT",
    
    # Package configuration
    packages=find_packages(),
    python_requires=">=3.10",
    
    # Dependencies
    install_requires=[
        "requests>=2.28.0",
        "python-dotenv>=0.21.0",
        "typing-extensions>=4.1.0",
        "pydantic>=2.0.0"
    ],
    
    # Dev dependencies
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pylint>=2.15.0",
            "mypy>=1.0.0",
            "black>=23.0.0"
        ]
    },
    
    # Entry points
    entry_points={
        "console_scripts": [
            "senddetections=sendDetections.__main__:main",
        ],
    },
    
    # Package data
    include_package_data=True,
    
    # Classifiers help users find your project
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Security",
    ],
)