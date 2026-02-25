"""
Accessibility Automation Agent - Setup Configuration
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="accessibility-automation-agent",
    version="0.1.0",
    author="adibgafur",
    description="AI-powered desktop automation for users without hands",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/adibgafur/accessibility-automation-agent",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Topic :: Accessibility",
        "Topic :: Office/Business",
    ],
    python_requires=">=3.11",
    entry_points={
        "console_scripts": [
            "accessibility-agent=main:main",
        ],
    },
)
