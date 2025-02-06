from typing import Any
import yaml
from fractal_healthcheck.checks import implementations
import logging
from fractal_healthcheck import LOGGER_NAME
from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from fractal_healthcheck.checks.CheckResults import CheckResult

logger = logging.getLogger(LOGGER_NAME)


class Check(BaseModel):
    name: str
    function_name: str
    kwargs: dict[str, Any] = Field(default_factory=dict)
    result: CheckResult | None = None

    @property
    def _function(self):
        return getattr(implementations, self.function_name)

    def run(self):
        self.result = self._function(**self.kwargs)


class CheckSuite(BaseModel):
    checks: list[Check]

    @field_validator("checks", mode="after")
    @classmethod
    def unique_names(cls, value: list[Check]) -> list[Check]:
        names = [_check.name for _check in value]
        if len(names) != len(set(names)):
            raise ValueError(f"Non-unique list of check names: {names}.")
        return value

    def run(self):
        for _check in self.checks:
            logger.info(f"['{_check.name}'] START")
            _check.run()
            logger.debug(_check.result)
            logger.info(f"['{_check.name}'] END")

    @property
    def any_failing(self) -> bool:
        """
        True if any of the completed check has success=False
        """
        return any(
            _check.result.success is False
            for _check in self.checks
            if _check.result is not None
        )

    def get_results(self) -> dict[str, CheckResult]:
        """
        Return the results as a dict: {name:check.results}
        """
        return {_check.name: _check.result for _check in self.checks}

    def get_failing_results(self) -> dict[str, CheckResult]:
        """
        Return the failing results as a dict: {name:check.results}
        """
        return {
            _check.name: _check.result
            for _check in self.checks
            if not _check.result.success
        }

    def get_non_failing_results(self) -> dict[str, CheckResult]:
        """
        Return the non-failing results as a dict: {name:check.results}
        """
        return {
            _check.name: _check.result
            for _check in self.checks
            if _check.result.success
        }


def load_check_suite(config_file: str) -> CheckSuite:
    with open(config_file, "r") as f:
        config_dict = yaml.safe_load(f)
    checks_suite = CheckSuite(**config_dict)
    return checks_suite
