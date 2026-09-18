# Copyright (c) 2026, Ngo Xuan Hieu and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from assessment_hub.exceptions import InvalidStateError
from assessment_hub.tests.utils import make_assessment, make_question, override_settings


class TestAssessment(IntegrationTestCase):
	def test_new_assessment_defaults_to_draft(self):
		doc = make_assessment()
		self.assertEqual(doc.status, "Draft")
		self.assertTrue(doc.name.startswith("ASM-"))

	def test_new_assessment_cannot_start_published(self):
		doc = frappe.get_doc({"doctype": "Assessment", "title": "Bad start", "status": "Published"})
		self.assertRaises(InvalidStateError, doc.insert)

	def test_publish_requires_an_active_question(self):
		doc = make_assessment()
		self.assertRaises(InvalidStateError, doc.publish)

	def test_inactive_questions_do_not_count_for_publishing(self):
		doc = make_assessment()
		make_question(doc.name, status="Inactive")
		doc.reload()
		self.assertRaises(InvalidStateError, doc.publish)

	def test_publish_without_questions_when_setting_enabled(self):
		override_settings(self, allow_publish_without_questions=1)
		doc = make_assessment()
		doc.publish()
		self.assertEqual(frappe.db.get_value("Assessment", doc.name, "status"), "Published")

	def test_publish_then_archive(self):
		doc = make_assessment()
		make_question(doc.name)
		doc.reload()
		doc.publish()
		doc.reload()
		doc.archive()
		self.assertEqual(frappe.db.get_value("Assessment", doc.name, "status"), "Archived")

	def test_draft_can_be_archived_directly(self):
		doc = make_assessment()
		doc.archive()
		self.assertEqual(frappe.db.get_value("Assessment", doc.name, "status"), "Archived")

	def test_published_cannot_return_to_draft(self):
		doc = make_assessment(status="Published")
		doc.status = "Draft"
		self.assertRaises(InvalidStateError, doc.save)

	def test_archived_assessment_is_read_only(self):
		doc = make_assessment(status="Archived")
		doc.title = "Renamed"
		self.assertRaises(InvalidStateError, doc.save)

	def test_title_html_is_sanitized_on_save(self):
		doc = make_assessment(title='Quiz <img src=x onerror="alert(1)">')
		stored = frappe.db.get_value("Assessment", doc.name, "title")
		self.assertNotIn("onerror", stored)
