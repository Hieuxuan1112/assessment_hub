import frappe
from frappe.tests import IntegrationTestCase

from assessment_hub.api.v1._response import api_endpoint
from assessment_hub.exceptions import ApiParameterError, InvalidStateError
from assessment_hub.tests.utils import call_api


def endpoint_raising(exc):
	@api_endpoint
	def endpoint():
		raise exc

	return endpoint


class TestApiResponse(IntegrationTestCase):
	def assertApiError(self, response, status, code):
		self.assertEqual(response.get("http_status_code"), status)
		self.assertEqual(len(response["errors"]), 1)
		self.assertEqual(response["errors"][0]["code"], code)
		self.assertTrue(response["errors"][0]["message"])
		self.assertEqual(frappe.local.message_log, [])

	def test_success_returns_value_without_errors(self):
		@api_endpoint
		def endpoint():
			return {"ok": True}

		result, response = call_api(endpoint)
		self.assertEqual(result, {"ok": True})
		self.assertNotIn("errors", response)
		self.assertNotIn("http_status_code", response)

	def test_exceptions_map_to_status_and_code(self):
		cases = [
			(ApiParameterError("page is invalid"), 400, "INVALID_PARAMETER"),
			(ApiParameterError("id is required", "MISSING_PARAMETER"), 400, "MISSING_PARAMETER"),
			(frappe.PermissionError("not allowed"), 403, "PERMISSION_DENIED"),
			(frappe.DoesNotExistError("missing"), 404, "NOT_FOUND"),
			(InvalidStateError("archived"), 409, "INVALID_STATE"),
			(frappe.MandatoryError("title"), 422, "VALIDATION_ERROR"),
			(frappe.ValidationError("bad value"), 422, "VALIDATION_ERROR"),
		]
		for exc, status, code in cases:
			with self.subTest(exception=type(exc).__name__, code=code):
				result, response = call_api(endpoint_raising(exc))
				self.assertIsNone(result)
				self.assertApiError(response, status, code)

	def test_empty_permission_message_gets_a_default(self):
		_, response = call_api(endpoint_raising(frappe.PermissionError()))
		self.assertEqual(
			response["errors"][0]["message"], "You do not have permission to perform this action."
		)

	def test_html_is_stripped_from_messages(self):
		exc = frappe.ValidationError("Assessment <strong>ASM-00001</strong> &amp; friends")
		_, response = call_api(endpoint_raising(exc))
		self.assertEqual(response["errors"][0]["message"], "Assessment ASM-00001 & friends")

	def test_frappe_throw_does_not_leak_server_messages(self):
		@api_endpoint
		def endpoint():
			frappe.throw("Boom")

		_, response = call_api(endpoint)
		self.assertApiError(response, 422, "VALIDATION_ERROR")

	def test_unexpected_error_is_logged_and_details_hidden(self):
		before = frappe.db.count("Error Log")
		_, response = call_api(endpoint_raising(RuntimeError("secret internals")))
		self.assertApiError(response, 500, "INTERNAL_ERROR")
		self.assertNotIn("secret internals", response["errors"][0]["message"])
		self.assertEqual(frappe.db.count("Error Log"), before + 1)

	def test_writes_are_rolled_back_when_endpoint_fails(self):
		title = f"Should vanish {frappe.generate_hash(length=6)}"

		@api_endpoint
		def endpoint():
			frappe.get_doc({"doctype": "Assessment", "title": title}).insert()
			raise frappe.ValidationError("fail after write")

		call_api(endpoint)
		self.assertFalse(frappe.db.exists("Assessment", {"title": title}))
