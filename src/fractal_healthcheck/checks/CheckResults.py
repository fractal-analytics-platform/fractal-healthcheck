from pydantic import BaseModel
from pydantic import ConfigDict


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
