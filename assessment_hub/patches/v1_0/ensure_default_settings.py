from assessment_hub.install import ensure_default_settings


def execute():
	"""Idempotent: store default Assessment Hub Settings on sites installed before settings existed."""
	ensure_default_settings()
