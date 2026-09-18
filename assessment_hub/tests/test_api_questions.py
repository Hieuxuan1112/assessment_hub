from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from assessment_hub.api.v1 import questions
from assessment_hub.assessment_hub.doctype.assessment_question.assessment_question import AssessmentQuestion
from assessment_hub.tests.utils import call_api, make_assessment, make_question, make_user

MANAGER = "ah-manager@example.com"
VIEWER = "ah-viewer@example.com"
OUTSIDER = "ah-outsider@example.com"
VALID_ANSWERS = [{"content": "Paris", "score": 1}, {"content": "Rome", "score": 0}]


class TestQuestionsApi(IntegrationTestCase):
	def setUp(self):
		make_user(MANAGER, ("Assessment Manager",))
		make_user(VIEWER, ("Assessment Viewer",))
		make_user(OUTSIDER, ())
		self.assessment = make_assessment(title=f"Questions API {frappe.generate_hash(length=8)}")
		self.addCleanup(frappe.set_user, "Administrator")

	def assertApiError(self, response, status, code):
		self.assertEqual(response.get("http_status_code"), status, response)
		self.assertEqual(response["errors"][0]["code"], code)

	def counts(self):
		return frappe.db.count("Assessment Question"), frappe.db.count("Assessment Answer")

	def create(self, **overrides):
		payload = {
			"assessment_id": self.assessment.name,
			"content": "<p>Capital of France?</p>",
			"answers": [dict(row) for row in VALID_ANSWERS],
		}
		payload.update(overrides)
		return call_api(questions.create_question, **payload)

	# ---- list_questions ---------------------------------------------------

	def test_list_orders_by_sort_order(self):
		third = make_question(self.assessment.name, content="<p>C</p>", sort_order=3)
		first = make_question(self.assessment.name, content="<p>A</p>", sort_order=1)
		second = make_question(self.assessment.name, content="<p>B</p>", sort_order=2)
		result, _ = call_api(questions.list_questions, assessment_id=self.assessment.name)
		self.assertEqual([item["id"] for item in result["items"]], [first.name, second.name, third.name])
		self.assertNotIn("answers", result["items"][0])
		self.assertFalse(result["pagination"]["has_more"])

	def test_list_status_filter_and_include_answers(self):
		make_question(self.assessment.name, content="<p>Active</p>")
		inactive = make_question(self.assessment.name, content="<p>Off</p>", status="Inactive")
		result, _ = call_api(
			questions.list_questions,
			assessment_id=self.assessment.name,
			status="Inactive",
			include_answers="true",
		)
		self.assertEqual([item["id"] for item in result["items"]], [inactive.name])
		self.assertEqual(len(result["items"][0]["answers"]), 2)

	def test_list_paginates(self):
		for i in range(3):
			make_question(self.assessment.name, content=f"<p>Q{i}</p>")
		result, _ = call_api(
			questions.list_questions, assessment_id=self.assessment.name, page_length=2, page=2
		)
		self.assertEqual(len(result["items"]), 1)
		self.assertEqual(result["pagination"]["start"], 2)

	def test_list_requires_assessment_id(self):
		_, response = call_api(questions.list_questions)
		self.assertApiError(response, 400, "MISSING_PARAMETER")

	def test_list_unknown_assessment_is_not_found(self):
		_, response = call_api(questions.list_questions, assessment_id="ASM-99999999")
		self.assertApiError(response, 404, "NOT_FOUND")

	def test_list_denied_without_role(self):
		frappe.set_user(OUTSIDER)
		_, response = call_api(questions.list_questions, assessment_id=self.assessment.name)
		self.assertApiError(response, 403, "PERMISSION_DENIED")

	# ---- create_question --------------------------------------------------

	def test_create_question_success(self):
		frappe.set_user(MANAGER)
		result, response = self.create(sort_order="5")
		self.assertNotIn("errors", response, response)
		self.assertEqual(result["assessment_id"], self.assessment.name)
		self.assertEqual(result["status"], "Active")
		self.assertEqual(result["sort_order"], 5)
		self.assertEqual([a["content"] for a in result["answers"]], ["Paris", "Rome"])
		self.assertEqual(frappe.db.count("Assessment Answer", {"parent": result["id"]}), 2)

	def test_create_accepts_answers_as_json_string(self):
		frappe.set_user(MANAGER)
		result, response = self.create(answers=frappe.as_json(VALID_ANSWERS))
		self.assertNotIn("errors", response, response)
		self.assertEqual(len(result["answers"]), 2)

	def test_viewer_cannot_create(self):
		frappe.set_user(VIEWER)
		before = self.counts()
		result, response = self.create()
		self.assertIsNone(result)
		self.assertApiError(response, 403, "PERMISSION_DENIED")
		self.assertEqual(self.counts(), before)

	def test_create_on_archived_assessment_is_conflict(self):
		archived = make_assessment(title="Archived target", status="Archived")
		frappe.set_user(MANAGER)
		_, response = self.create(assessment_id=archived.name)
		self.assertApiError(response, 409, "INVALID_STATE")

	def test_create_on_unknown_assessment_is_not_found(self):
		frappe.set_user(MANAGER)
		_, response = self.create(assessment_id="ASM-99999999")
		self.assertApiError(response, 404, "NOT_FOUND")

	def test_create_parameter_errors(self):
		frappe.set_user(MANAGER)
		cases = [
			({"content": ""}, "MISSING_PARAMETER"),
			({"answers": None}, "MISSING_PARAMETER"),
			({"answers": {"content": "x"}}, "INVALID_PARAMETER"),
			({"answers": [{"content": "A", "score": "high"}]}, "INVALID_PARAMETER"),
			({"status": "Hidden"}, "INVALID_PARAMETER"),
			({"sort_order": "0"}, "INVALID_PARAMETER"),
		]
		for overrides, code in cases:
			with self.subTest(overrides=overrides):
				_, response = self.create(**overrides)
				self.assertApiError(response, 400, code)

	def test_invalid_answer_rolls_back_everything(self):
		frappe.set_user(MANAGER)
		before = self.counts()
		answers = [{"content": "Paris", "score": 1}, {"content": "Rome", "score": -5}]
		result, response = self.create(answers=answers)
		self.assertIsNone(result)
		self.assertApiError(response, 422, "VALIDATION_ERROR")
		self.assertEqual(self.counts(), before)

	def test_failure_after_rows_are_written_rolls_back_question_and_answers(self):
		frappe.set_user(MANAGER)
		before = self.counts()
		with patch.object(
			AssessmentQuestion,
			"on_update",
			create=True,
			side_effect=RuntimeError("simulated crash after insert"),
		):
			result, response = self.create()
		self.assertIsNone(result)
		self.assertApiError(response, 500, "INTERNAL_ERROR")
		self.assertEqual(self.counts(), before)
