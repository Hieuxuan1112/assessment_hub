import types
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from assessment_hub.api.v1 import assessments
from assessment_hub.api.v1._ratelimit import counter_key
from assessment_hub.tests.utils import call_api, make_user, override_settings

USER = "ah-ratelimit-a@example.com"
OTHER_USER = "ah-ratelimit-b@example.com"
FIXED_NOW = 1_800_000_000  # one fixed minute, so a test can never straddle a window boundary
WINDOW = FIXED_NOW // 60


class TestApiRateLimit(IntegrationTestCase):
	def setUp(self):
		make_user(USER, ("Assessment Viewer",))
		make_user(OTHER_USER, ("Assessment Viewer",))
		for user in (USER, OTHER_USER):
			frappe.cache.delete(counter_key(user, WINDOW))
		clock = patch("assessment_hub.api.v1._ratelimit.time.time", return_value=FIXED_NOW)
		clock.start()
		self.addCleanup(clock.stop)
		self.addCleanup(frappe.set_user, "Administrator")

	def as_http_request(self):
		"""Rate limiting only applies to real HTTP requests (frappe.request is set)."""
		previous = getattr(frappe.local, "request", None)
		frappe.local.request = types.SimpleNamespace(method="GET")
		self.addCleanup(setattr, frappe.local, "request", previous)

	def call(self, user):
		# Registered after override_settings, so it runs first and the settings restore
		# (which needs write permission) happens as Administrator.
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(user)
		return call_api(assessments.list_assessments, page_length=1)

	def test_requests_over_the_limit_get_429(self):
		override_settings(self, api_rate_limit_per_minute=2)
		self.as_http_request()

		for _ in range(2):
			_, response = self.call(USER)
			self.assertNotIn("errors", response, response)

		result, response = self.call(USER)
		self.assertIsNone(result)
		self.assertEqual(response.get("http_status_code"), 429)
		self.assertEqual(response["errors"][0]["code"], "RATE_LIMITED")

	def test_limit_is_per_user(self):
		override_settings(self, api_rate_limit_per_minute=1)
		self.as_http_request()

		self.call(USER)
		_, blocked = self.call(USER)
		_, other = self.call(OTHER_USER)

		self.assertEqual(blocked.get("http_status_code"), 429)
		self.assertNotIn("errors", other, other)

	def test_zero_disables_the_limit(self):
		override_settings(self, api_rate_limit_per_minute=0)
		self.as_http_request()
		for _ in range(5):
			_, response = self.call(USER)
			self.assertNotIn("errors", response, response)

	def test_calls_without_an_http_request_are_not_limited(self):
		override_settings(self, api_rate_limit_per_minute=1)
		for _ in range(3):
			_, response = self.call(USER)
			self.assertNotIn("errors", response, response)

	def test_a_new_minute_starts_a_fresh_count(self):
		override_settings(self, api_rate_limit_per_minute=1)
		self.as_http_request()
		self.call(USER)
		_, blocked = self.call(USER)
		self.assertEqual(blocked.get("http_status_code"), 429)

		self.addCleanup(frappe.cache.delete, counter_key(USER, WINDOW + 1))
		with patch("assessment_hub.api.v1._ratelimit.time.time", return_value=FIXED_NOW + 60):
			_, response = self.call(USER)
		self.assertNotIn("errors", response, response)
