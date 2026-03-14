from setuptools import setup, find_packages

setup(
    name="kodoseq",
    version="0.1.0",
    description="KODOSEQ — Generative MIDI Sequencer Engine",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[],
    extras_require={
        "midi": ["python-rtmidi>=1.5.0"],
        "dev": ["pytest>=7.0", "pytest-cov>=4.0"],
    },
)
