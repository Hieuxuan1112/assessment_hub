"""Per-user request limiter for the Partner API (fixed one-minute windows, counted in Redis).

Only real HTTP requests are counted: internal calls (tests, `bench execute`) have no
`frappe.request` and are never limited. The limit comes from
`Assessment Hub Settings.api_rate_limit_per_minute`; 0 turns the limiter off.
"""

import time

import frappe
from frappe import _
from frappe.utils import cint

from assessment_hub.utils.settings import get_settings

WINDOW_SECONDS = 60


def counter_key(user: str, window: int) -> bytes:
	return frappe.cache.make_key(f"assessment_hub:ratelimit:{user}:{window}")


def check_rate_limit() -> None:
	if not frappe.request:
		return
	limit = cint(get_settings().api_rate_limit_per_minute)
	if limit <= 0:
		return

	key = counter_key(frappe.session.user, int(time.time()) // WINDOW_SECONDS)
	count = frappe.cache.incrby(key, 1)
	if count == 1:
		frappe.cache.expire(key, WINDOW_SECONDS)
	if count > limit:
		raise frappe.RateLimitExceededError(
			_("Rate limit exceeded: at most {0} requests per minute. Please retry shortly.").format(limit)
		)
