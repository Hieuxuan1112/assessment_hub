from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from assessment_hub.api.v1 import assessments
from assessment_hub.tests.utils import (
	call_api,
	make_assessment,
	make_question,
	make_user,
	override_settings,
)

MANAGER = "ah-manager@example.com"
VIEWER = "ah-viewer@example.com"
OUTSIDER = "ah-outsider@example.com"
ASSESSMENT_KEYS = {"id", "title", "description", "status", "created_at", "updated_at"}


class TestAssessmentsApi(IntegrationTestCase):
	def setUp(self):
		make_user(MANAGER, ("Assessment Manager",))
		make_user(VIEWER, ("Assessment Viewer",))
		make_user(OUTSIDER, ())
		self.prefix = f"ApiTest-{frappe.generate_hash(length=8)}"
		self.addCleanup(frappe.set_user, "Administrator")

	def assertApiError(self, response, status, code):
		self.assertEqual(response.get("http_status_code"), status, response)
		self.assertEqual(response["errors"][0]["code"], code)

	def list_ids(self, **kwargs):
		result, response = call_api(assessments.list_assessments, search=self.prefix, **kwargs)
		self.assertNotIn("errors", response, response)
		return [item["id"] for item in result["items"]], result["pagination"]

	# ---- list_assessments -------------------------------------------------

	def test_list_returns_items_and_pagination(self):
		docs = [make_assessment(title=f"{self.prefix} {i}") for i in range(3)]

		first_ids, first_page = self.list_ids(page_length=2)
		self.assertEqual(len(first_ids), 2)
		self.assertEqual(first_page, {"start": 0, "page_length": 2, "has_more": True, "next_start": 2})

		second_ids, second_page = self.list_ids(page_length=2, start=2)
		self.assertEqual(len(second_ids), 1)
		self.assertFalse(second_page["has_more"])
		self.assertIsNone(second_page["next_start"])
		self.assertEqual(set(first_ids + second_ids), {doc.name for doc in docs})

		page_ids, _ = self.list_ids(page_length=2, page=2)
		self.assertEqual(page_ids, second_ids)

	def test_item_shape(self):
		make_assessment(title=f"{self.prefix} shape", description="About Python")
		result, _ = call_api(assessments.list_assessments, search=self.prefix)
		self.assertEqual(set(result["items"][0]), ASSESSMENT_KEYS)
		self.assertEqual(result["items"][0]["description"], "About Python")

	def test_default_page_length_comes_from_settings(self):
		override_settings(self, default_page_length=2, max_page_length=100)
		for i in range(3):
			make_assessment(title=f"{self.prefix} {i}")
		ids, pagination = self.list_ids()
		self.assertEqual(len(ids), 2)
		self.assertEqual(pagination["page_length"], 2)

	def test_page_length_above_max_is_rejected(self):
		override_settings(self, default_page_length=2, max_page_length=5)
		_, response = call_api(assessments.list_assessments, page_length=6)
		self.assertApiError(response, 400, "INVALID_PARAMETER")

	def test_start_and_page_together_are_rejected(self):
		_, response = call_api(assessments.list_assessments, start=0, page=1)
		self.assertApiError(response, 400, "INVALID_PARAMETER")

	def test_status_filter(self):
		draft = make_assessment(title=f"{self.prefix} draft")
		published = make_assessment(title=f"{self.prefix} published", status="Published")
		ids, _ = self.list_ids(status="Published")
		self.assertEqual(ids, [published.name])
		self.assertNotIn(draft.name, ids)

	def test_invalid_status_is_rejected(self):
		_, response = call_api(assessments.list_assessments, status="Deleted")
		self.assertApiError(response, 400, "INVALID_PARAMETER")

	def test_search_treats_like_wildcards_literally(self):
		literal = make_assessment(title=f"{self.prefix} 100% ready")
		make_assessment(title=f"{self.prefix} 1000 ready")
		result, _ = call_api(assessments.list_assessments, search=f"{self.prefix} 100%")
		self.assertEqual([item["id"] for item in result["items"]], [literal.name])

	def test_updated_since_filters_and_sorts_ascending(self):
		oldest = make_assessment(title=f"{self.prefix} a")
		middle = make_assessment(title=f"{self.prefix} b")
		newest = make_assessment(title=f"{self.prefix} c")
		for doc, stamp in (
			(oldest, "2026-01-01 10:00:00"),
			(middle, "2026-01-02 10:00:00"),
			(newest, "2026-01-03 10:00:00"),
		):
			frappe.db.set_value("Assessment", doc.name, "modified", stamp, update_modified=False)

		ids, _ = self.list_ids(updated_since="2026-01-02 00:00:00")
		self.assertEqual(ids, [middle.name, newest.name])

	def test_invalid_updated_since_is_rejected(self):
		_, response = call_api(assessments.list_assessments, updated_since="yesterday-ish")
		self.assertApiError(response, 400, "INVALID_PARAMETER")

	def test_viewer_can_list(self):
		make_assessment(title=f"{self.prefix} visible")
		frappe.set_user(VIEWER)
		ids, _ = self.list_ids()
		self.assertEqual(len(ids), 1)

	def test_user_without_role_is_denied(self):
		frappe.set_user(OUTSIDER)
		result, response = call_api(assessments.list_assessments)
		self.assertIsNone(result)
		self.assertApiError(response, 403, "PERMISSION_DENIED")

	# ---- get_assessment ---------------------------------------------------

	def test_get_requires_id(self):
		_, response = call_api(assessments.get_assessment)
		self.assertApiError(response, 400, "MISSING_PARAMETER")

	def test_get_unknown_id_is_not_found(self):
		_, response = call_api(assessments.get_assessment, id="ASM-99999999")
		self.assertApiError(response, 404, "NOT_FOUND")

	def test_get_without_questions(self):
		doc = make_assessment(title=f"{self.prefix} solo")
		result, _ = call_api(assessments.get_assessment, id=doc.name)
		self.assertEqual(set(result), ASSESSMENT_KEYS)
		self.assertEqual(result["id"], doc.name)

	def test_get_with_questions_nests_ordered_questions_and_answers(self):
		doc = make_assessment(title=f"{self.prefix} nested")
		second = make_question(doc.name, content="<p>Second</p>", sort_order=2)
		first = make_question(
			doc.name,
			content="<p>First</p>",
			sort_order=1,
			answers=[
				{"content": "B", "score": 0, "sort_order": 2},
				{"content": "A", "score": 1, "sort_order": 1},
			],
		)

		result, _ = call_api(assessments.get_assessment, id=doc.name, include_questions="1")

		self.assertEqual([q["id"] for q in result["questions"]], [first.name, second.name])
		self.assertEqual([a["content"] for a in result["questions"][0]["answers"]], ["A", "B"])
		self.assertEqual(set(result["questions"][0]["answers"][0]), {"id", "content", "score", "sort_order"})

	def test_get_rejects_invalid_include_questions(self):
		doc = make_assessment(title=f"{self.prefix} flag")
		_, response = call_api(assessments.get_assessment, id=doc.name, include_questions="maybe")
		self.assertApiError(response, 400, "INVALID_PARAMETER")

	def test_get_denied_for_user_without_role(self):
		doc = make_assessment(title=f"{self.prefix} private")
		frappe.set_user(OUTSIDER)
		_, response = call_api(assessments.get_assessment, id=doc.name)
		self.assertApiError(response, 403, "PERMISSION_DENIED")

	def test_include_questions_query_count_does_not_grow_with_questions(self):
		small = make_assessment(title=f"{self.prefix} small")
		make_question(small.name)
		large = make_assessment(title=f"{self.prefix} large")
		for i in range(6):
			make_question(large.name, content=f"<p>Question {i}</p>")

		for name in (small.name, large.name):  # warm metadata caches
			call_api(assessments.get_assessment, id=name, include_questions=1)

		small_count = self.count_queries(
			lambda: call_api(assessments.get_assessment, id=small.name, include_questions=1)
		)
		large_count = self.count_queries(
			lambda: call_api(assessments.get_assessment, id=large.name, include_questions=1)
		)
		self.assertEqual(small_count, large_count)

	def count_queries(self, fn) -> int:
		counter = {"queries": 0}
		db = frappe.local.db
		original_sql = db.sql

		def counting_sql(*args, **kwargs):
			counter["queries"] += 1
			return original_sql(*args, **kwargs)

		with patch.object(db, "sql", side_effect=counting_sql):
			fn()
		return counter["queries"]
