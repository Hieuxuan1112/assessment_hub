# Copyright (c) 2026, Ngo Xuan Hieu and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from assessment_hub.exceptions import InvalidStateError
from assessment_hub.tests.utils import make_assessment, make_question, override_settings


class TestAssessmentQuestion(IntegrationTestCase):
	def test_cannot_add_question_to_archived_assessment(self):
		assessment = make_assessment(status="Archived")
		self.assertRaises(InvalidStateError, make_question, assessment.name)

	def test_cannot_edit_question_after_assessment_is_archived(self):
		assessment = make_assessment()
		question = make_question(assessment.name)
		assessment.reload()
		assessment.archive()

		question.reload()
		question.content = "<p>Changed</p>"
		self.assertRaises(InvalidStateError, question.save)

	def test_cannot_move_question_out_of_archived_assessment(self):
		archived = make_assessment(title="Soon archived")
		question = make_question(archived.name)
		archived.reload()
		archived.archive()
		open_assessment = make_assessment(title="Open")

		question.reload()
		question.assessment = open_assessment.name
		self.assertRaises(InvalidStateError, question.save)

	def test_unknown_assessment_is_rejected(self):
		self.assertRaises(frappe.ValidationError, make_question, "ASM-DOES-NOT-EXIST")

	def test_sort_order_auto_increments_per_assessment(self):
		assessment = make_assessment()
		first = make_question(assessment.name, content="<p>First</p>")
		second = make_question(assessment.name, content="<p>Second</p>")
		explicit = make_question(assessment.name, content="<p>Third</p>", sort_order=10)
		fourth = make_question(assessment.name, content="<p>Fourth</p>")
		self.assertEqual(
			[first.sort_order, second.sort_order, explicit.sort_order, fourth.sort_order],
			[1, 2, 10, 11],
		)

	def test_negative_sort_order_is_rejected(self):
		assessment = make_assessment()
		self.assertRaises(frappe.ValidationError, make_question, assessment.name, sort_order=-1)

	def test_requires_minimum_answers(self):
		assessment = make_assessment()
		self.assertRaises(frappe.ValidationError, make_question, assessment.name, answers=[])

	def test_minimum_answers_comes_from_settings(self):
		override_settings(self, min_answers_per_question=3)
		assessment = make_assessment()
		self.assertRaises(frappe.ValidationError, make_question, assessment.name)

	def test_blank_answer_content_is_rejected(self):
		assessment = make_assessment()
		answers = [{"content": "   ", "score": 1}]
		self.assertRaises(frappe.ValidationError, make_question, assessment.name, answers=answers)

	def test_negative_score_is_rejected(self):
		assessment = make_assessment()
		answers = [{"content": "A", "score": -1}]
		self.assertRaises(frappe.ValidationError, make_question, assessment.name, answers=answers)

	def test_duplicate_answer_content_is_rejected(self):
		assessment = make_assessment()
		answers = [{"content": "Yes", "score": 1}, {"content": " yes ", "score": 0}]
		self.assertRaises(frappe.ValidationError, make_question, assessment.name, answers=answers)

	def test_answer_sort_order_defaults_to_position(self):
		assessment = make_assessment()
		question = make_question(
			assessment.name,
			answers=[
				{"content": "A", "score": 1},
				{"content": "B", "score": 0, "sort_order": 5},
				{"content": "C", "score": 0},
			],
		)
		self.assertEqual([row.sort_order for row in question.answers], [1, 5, 3])

	def test_script_in_content_is_sanitized(self):
		assessment = make_assessment()
		question = make_question(assessment.name, content="<p>Hi</p><script>alert(1)</script>")
		stored = frappe.db.get_value("Assessment Question", question.name, "content")
		self.assertNotIn("<script", stored)

	def test_composite_index_on_assessment_and_sort_order(self):
		rows = frappe.db.sql("SHOW INDEX FROM `tabAssessment Question`", as_dict=True)
		columns = {row.Column_name for row in rows if row.Key_name == "assessment_sort_order_index"}
		self.assertEqual(columns, {"assessment", "sort_order"})
