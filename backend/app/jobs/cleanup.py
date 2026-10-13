"""backend/app/jobs/cleanup.py"""
"""Delete expired uploads and cache entries. Runs hourly inside the app, or by hand:
    python -m app.jobs.cleanup
"""
from app.services.orchestrator.pipeline import Services


def run_cleanup(svc: Services) -> dict[str, int]:
    return {"uploads": svc.storage.cleanup(), "cache": svc.cache.cleanup()}


if __name__ == "__main__":
    from app.api.deps import get_services

    print(run_cleanup(get_services()))
