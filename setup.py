#!/usr/bin/env python3
"""
Setup script for MCP Reliability Lab.
Enables installation via pip.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README for long description
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text() if (this_directory / "README.md").exists() else ""

setup(
    name="mcp-reliability-lab",
    version="1.0.0",
    author="MCP Lab Team",
    author_email="team@mcp-lab.com",
    description="Scientific testing framework for Model Context Protocol servers",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/mcp-reliability-lab",
    project_urls={
        "Documentation": "https://docs.mcp-lab.com",
        "Source": "https://github.com/yourusername/mcp-reliability-lab",
        "Tracker": "https://github.com/yourusername/mcp-reliability-lab/issues",
    },
    packages=find_packages(exclude=["tests", "tests.*", "docs", "docs.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Framework :: FastAPI",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "mcp>=0.1.0",
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "httpx>=0.24.0",
        "jinja2>=3.1.0",
        "python-multipart>=0.0.6",
        "hypothesis>=6.80.0",
        "aiofiles>=23.2.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "black>=23.7.0",
            "isort>=5.12.0",
            "mypy>=1.5.0",
            "flake8>=6.1.0",
        ],
        "docs": [
            "mkdocs>=1.5.0",
            "mkdocs-material>=9.2.0",
            "mkdocstrings[python]>=0.22.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "mcp-lab=mcp_reliability_lab.cli:main",
            "mcp-lab-server=mcp_reliability_lab.web_ui:start_server",
        ],
    },
    include_package_data=True,
    package_data={
        "mcp_reliability_lab": [
            "templates/*.html",
            "templates/partials/*.html",
            "static/*",
        ],
    },
    zip_safe=False,
)