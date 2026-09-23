"""Source adapters.

Each adapter module exposes `fetch_jobs(source) -> list[Job]` and may also define:
  - `load_details(job)`: fill in job.description (and refine location) for one job. Called only
    for new jobs that pass the title filter, for sources whose list endpoint is too sparse.
  - `POLL_EVERY`: a timedelta; the source is skipped until that long after its last success.

To add a new kind of source, write a module like the ones here and register it below.
"""

from . import ashby, greenhouse, lever, simplify, workday

ADAPTERS = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "workday": workday,
    "simplify": simplify,
}
