# Fractal Healthcheck

<p align="center">
  <img src="https://raw.githubusercontent.com/fractal-analytics-platform/fractal-logos/refs/heads/main/common/fractal_logo.png" alt="Fractal logo" width="150">
</p>

[![PyPI version](https://img.shields.io/pypi/v/fractal-healthcheck?color=gree)](https://pypi.org/project/fractal-healthcheck/)
[![License](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![CI Status](https://github.com/fractal-analytics-platform/fractal-healthcheck/actions/workflows/ci.yml/badge.svg)](https://github.com/fractal-analytics-platform/fractal-healthcheck/actions/workflows/ci.yml?query=branch%3Amain)

[Fractal](https://fractal-analytics-platform.github.io/) is a framework developed at the [BioVisionCenter](https://www.biovisioncenter.uzh.ch/en.html) to process bioimaging data at scale in the OME-Zarr format and prepare the images for interactive visualization.

![Fractal_overview](https://github.com/user-attachments/assets/666c8797-2594-4b8e-b1d2-b43fca66d1df)

Fractal healthcheck is a monitoring tool which helps in operating Fractal instances.
Find more information about Fractal in general and the other repositories at
the [Fractal home page](https://fractal-analytics-platform.github.io).


# Get started
```console
$ python -m venv venv

$ source venv/bin/activate

$ python -m pip install -e .
[...]
Successfully installed annotated-types-0.7.0 bumpver-2024.1130 click-8.1.8 colorama-0.4.6 dnspython-2.7.0 email-validator-2.2.0 fractal-healthcheck-0.0.1 idna-3.10 lexid-2021.1006 psutil-6.1.1 pydantic-2.10.4 pydantic-core-2.27.2 pyyaml-6.0.2 toml-0.10.2 typing-extensions-4.12.2

$ fractal-health
Usage: fractal-health [OPTIONS] CONFIG_FILE
Try 'fractal-health --help' for help.

Error: Missing argument 'CONFIG_FILE'.
```

# Development

```console
$ python -m venv venv

$ source venv/bin/activate

$ python -m pip install -e .[dev]
[...]

$ pre-commit install
[...]
```

## How to make a release
From the development environment:
```
bumpver update --patch --dry
```

# Contributors and license

Fractal was conceived in the Liberali Lab at the Friedrich Miescher Institute for Biomedical Research and in the Pelkmans Lab at the University of Zurich by
[@jluethi](https://github.com/jluethi) and [@gusqgm](https://github.com/gusqgm). The Fractal project is now developed at the
[BioVisionCenter](https://www.biovisioncenter.uzh.ch/en.html) at the University of Zurich and the project lead is with [@jluethi](https://github.com/jluethi).
The core development is done under contract by [eXact lab S.r.l.](https://www.exact-lab.it).

Unless otherwise specified, Fractal components are released under the BSD 3-Clause License, and copyright is with the BioVisionCenter at the University of Zurich.