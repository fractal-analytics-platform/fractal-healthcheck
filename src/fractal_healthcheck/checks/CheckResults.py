import logging
from pydantic import BaseModel
from pydantic import ConfigDict
import textwrap


class CheckResult(BaseModel):
    log: str = "N/A"
    exception: Exception | None = None
    success: bool = True

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def status(self) -> str:
        if self.success:
            return "PASS"
        else:
            return "FAIL"

    @property
    def full_log(self) -> str:
        if self.exception is not None:
            # exceptions from subprocess have some useful attributes, try to include them
            try:
                log_str = f"{self.exception.__class__}: {self.exception.args[0]}, stderr: {self.exception.stderr}"
            except (AttributeError, IndexError):
                log_str = f"{self.exception.__class__}: {self.exception}"
        else:
            log_str = self.log

        return log_str.strip("\n") + "\n"

    def format_for_report(self, name: str, max_log_size: int) -> str:
        log = self.full_log
        if len(log) > max_log_size:
            logging.warning(f"{len(log)=} is larger than {max_log_size=}, truncate")
            log = f"[TRUNCATED]\n{log[:max_log_size]}"

        return (
            f"Check: {name}\n"
            f"Status: {self.status}\n"
            f"Logs:\n{textwrap.indent(log, '> ')}\n"
            "----\n\n"
        )
