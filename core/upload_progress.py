"""Parse immich-go 0.32 `--no-ui` output and its --log-file into live stats.

Qt-free. Two sources:
- stdout progress line: "Immich read 42%, Assets found: 3, Upload errors: 0, Uploaded 2"
- log file per-file events: "... INF uploaded successfully file=Folder:a.jpg"
"""

import re
from dataclasses import dataclass, field

_PROGRESS_RE = re.compile(
    r"Immich read (\d+)%, Assets found: (\d+), Upload errors: (\d+), Uploaded (\d+)"
)
_REPORT_RE = re.compile(
    r"^\s*(Total Assets|Processed|Discarded|Errors|Pending):\s+(\d+)", re.M
)

# event text in the log -> stat bucket (same mapping as Immich Upload)
_EVENTS = (
    (re.compile(r" discovered (image|video) file="), "discovered"),
    (re.compile(r" (uploaded successfully|server asset upgraded) file="), "uploaded"),
    (
        re.compile(
            r" (server has duplicate|discarded local duplicate|discarded server better|metadata updated) file="
        ),
        "duplicates",
    ),
    (
        re.compile(
            r" (upload failed|server error|file access error|incomplete processing) file="
        ),
        "errors",
    ),
    (
        re.compile(r" discarded (banned|unsupported|filtered|not selected) file="),
        "skipped",
    ),
)


@dataclass
class UploadStats:
    immich_read_pct: int = 0
    found: int = 0
    uploaded: int = 0
    duplicates: int = 0
    skipped: int = 0
    errors: int = 0
    report: dict[str, int] = field(default_factory=dict)
    _seen: dict[str, set[str]] = field(default_factory=dict, repr=False)

    @property
    def done(self) -> int:
        return self.uploaded + self.duplicates + self.skipped + self.errors

    def feed_stdout(self, text: str) -> None:
        matches = _PROGRESS_RE.findall(text)
        if matches:
            pct, found, errs, up = (int(x) for x in matches[-1])
            self.immich_read_pct = min(pct, 100)
            self.found = max(self.found, found)
            self.errors = max(self.errors, errs)
            self.uploaded = max(self.uploaded, up)
        for name, val in _REPORT_RE.findall(text):
            self.report[name] = int(val)

    def feed_log_line(self, line: str) -> None:
        for rx, bucket in _EVENTS:
            if rx.search(line):
                f = line.split(" file=", 1)[1].split(" reason=", 1)[0].strip()
                seen = self._seen.setdefault(bucket, set())
                seen.add(f)
                attr = "found" if bucket == "discovered" else bucket
                setattr(self, attr, max(getattr(self, attr), len(seen)))
                return
