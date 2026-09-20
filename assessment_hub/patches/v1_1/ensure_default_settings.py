from assessment_hub.install import ensure_default_settings


def execute():
	"""Idempotent: store the new api_rate_limit_per_minute default on sites installed with v1.0.0."""
	ensure_default_settings()
