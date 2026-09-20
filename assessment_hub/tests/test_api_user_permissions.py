import frappe
from frappe.tests import IntegrationTestCase

from assessment_hub.api.v1 import assessments, questions
from assessment_hub.tests.utils import call_api, make_assessment, make_question, make_user

VIEWER = "ah-up-viewer@example.com"
MANAGER = "ah-up-manager@example.com"


class TestApiUserPermissions(IntegrationTestCase):
	"""A User Permission on Assessment must narrow what the Partner API returns and accepts."""

	def setUp(self):
		make_user(VIEWER, ("Assessment Viewer",))
		make_user(MANAGER, ("Assessment Manager",))
		self.prefix = f"UP-{frappe.generate_hash(length=8)}"
		self.allowed = make_assessment(title=f"{self.prefix} allowed")
		self.blocked = make_assessment(title=f"{self.prefix} blocked")
		make_question(self.allowed.name, content="<p>Allowed question</p>")
		make_question(self.blocked.name, content="<p>Blocked question</p>")
		for user in (VIEWER, MANAGER):
			frappe.get_doc(
				{
					"doctype": "User Permission",
					"user": user,
					"allow": "Assessment",
					"for_value": self.allowed.name,
					"apply_to_all_doctypes": 1,
				}
			).insert()
		self.addCleanup(frappe.set_user, "Administrator")

	def assertApiError(self, response, status, code):
		self.assertEqual(response.get("http_status_code"), status, response)
		self.assertEqual(response["errors"][0]["code"], code)

	def test_list_assessments_only_returns_permitted_records(self):
		frappe.set_user(VIEWER)
		result, response = call_api(assessments.list_assessments, search=self.prefix)
		self.assertNotIn("errors", response, response)
		self.assertEqual([item["id"] for item in result["items"]], [self.allowed.name])

	def test_get_assessment_outside_user_permission_is_forbidden(self):
		frappe.set_user(VIEWER)
		_, response = call_api(assessments.get_assessment, id=self.blocked.name)
		self.assertApiError(response, 403, "PERMISSION_DENIED")

	def test_get_assessment_inside_user_permission_works(self):
		frappe.set_user(VIEWER)
		result, response = call_api(assessments.get_assessment, id=self.allowed.name, include_questions=1)
		self.assertNotIn("errors", response, response)
		self.assertEqual(len(result["questions"]), 1)

	def test_list_questions_outside_user_permission_is_forbidden(self):
		frappe.set_user(VIEWER)
		_, response = call_api(questions.list_questions, assessment_id=self.blocked.name)
		self.assertApiError(response, 403, "PERMISSION_DENIED")

	def test_list_questions_inside_user_permission_works(self):
		frappe.set_user(VIEWER)
		result, response = call_api(questions.list_questions, assessment_id=self.allowed.name)
		self.assertNotIn("errors", response, response)
		self.assertEqual(len(result["items"]), 1)

	def test_manager_cannot_create_question_outside_user_permission(self):
		frappe.set_user(MANAGER)
		before = frappe.db.count("Assessment Question")
		_, response = call_api(
			questions.create_question,
			assessment_id=self.blocked.name,
			content="<p>Nope</p>",
			answers=[{"content": "A", "score": 1}],
		)
		self.assertApiError(response, 403, "PERMISSION_DENIED")
		self.assertEqual(frappe.db.count("Assessment Question"), before)

	def test_manager_can_create_question_inside_user_permission(self):
		frappe.set_user(MANAGER)
		result, response = call_api(
			questions.create_question,
			assessment_id=self.allowed.name,
			content="<p>Fine</p>",
			answers=[{"content": "A", "score": 1}],
		)
		self.assertNotIn("errors", response, response)
		self.assertEqual(result["assessment_id"], self.allowed.name)
