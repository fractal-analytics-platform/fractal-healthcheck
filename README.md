# fractal-healthcheck
Work-in-progress tool to monitor a Fractal instance


## Get started
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

## Development

```console
$ python -m venv venv

$ source venv/bin/activate

$ python -m pip install -e .[dev]
[...]

$ pre-commit install
[...]
```

### How to make a release
From the development environment:
```
bumpver update --patch --dry
```
