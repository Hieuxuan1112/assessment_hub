from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

import assessment_hub.api
from assessment_hub.api.v1 import assessments, questions

API_DIR = Path(assessment_hub.api.__file__).parent
FORBIDDEN_SNIPPETS = ("ignore_permissions", "frappe.db.sql", "allow_guest")
ENDPOINT_METHODS = {
	assessments.list_assessments: ["GET"],
	assessments.get_assessment: ["GET"],
	questions.list_questions: ["GET"],
	questions.create_question: ["POST"],
}


class TestApiSecurity(IntegrationTestCase):
	def test_api_code_never_bypasses_permissions_or_uses_raw_sql(self):
		files = sorted(API_DIR.rglob("*.py"))
		self.assertTrue(files)
		for path in files:
			source = path.read_text(encoding="utf-8")
			for snippet in FORBIDDEN_SNIPPETS:
				with self.subTest(file=path.name, snippet=snippet):
					self.assertNotIn(snippet, source)

	def test_endpoints_are_whitelisted_for_logged_in_users_with_fixed_http_methods(self):
		for fn, methods in ENDPOINT_METHODS.items():
			with self.subTest(endpoint=fn.__name__):
				self.assertIn(fn, frappe.whitelisted)
				self.assertNotIn(fn, frappe.guest_methods)
				self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[fn], methods)
