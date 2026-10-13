"""backend/app/services/framework/loader.py"""
import json
from functools import lru_cache
from pathlib import Path

import jsonschema
import yaml

from app.core.errors import FrameworkError
from app.schemas.framework import Framework


def load_framework(path: Path, schema_path: Path) -> Framework:
    """Load the framework YAML, validate it against the JSON schema and basic consistency rules."""
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise FrameworkError(f"Could not read the framework files: {exc}") from exc

    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as exc:
        raise FrameworkError(f"Framework YAML is invalid: {exc.message}") from exc

    fw = Framework(**data)

    ids = [c.id for c in fw.all_criteria()]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise FrameworkError(f"Duplicate criterion ids: {sorted(dupes)}")

    keys = [c.key for c in fw.components]
    if len(keys) != len(set(keys)):
        raise FrameworkError("Duplicate component keys.")

    for c in fw.all_criteria():
        if c.tier == "A" and not c.rule:
            raise FrameworkError(f"Tier A criterion {c.id} needs a rule.")
        if c.tier == "B" and not (c.rule or c.ml_label):
            raise FrameworkError(f"Tier B criterion {c.id} needs a rule or an ml_label.")
    return fw


@lru_cache(maxsize=4)
def get_framework(path: str, schema_path: str) -> Framework:
    """Cached loader (keyed by file paths)."""
    return load_framework(Path(path), Path(schema_path))