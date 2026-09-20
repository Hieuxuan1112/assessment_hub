from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from assessment_hub.api.v1 import questions
from assessment_hub.api.v1._idempotency import find_existing
from assessment_hub.tests.utils import call_api, make_assessment, make_user

MANAGER = "ah-idem-a@example.com"
OTHER_MANAGER = "ah-idem-b@example.com"
ANSWERS = [{"content": "Yes", "score": 1}, {"content": "No", "score": 0}]


class TestApiIdempotency(IntegrationTestCase):
	def setUp(self):
		make_user(MANAGER, ("Assessment Manager",))
		make_user(OTHER_MANAGER, ("Assessment Manager",))
		self.assessment = make_assessment(title=f"Idempotency {frappe.generate_hash(length=8)}")
		self.key = f"key-{frappe.generate_hash(length=10)}"
		self.addCleanup(frappe.set_user, "Administrator")

	def create(self, user=MANAGER, **overrides):
		frappe.set_user(user)
		payload = {
			"assessment_id": self.assessment.name,
			"content": "<p>Is it idempotent?</p>",
			"answers": [dict(row) for row in ANSWERS],
			"idempotency_key": self.key,
		}
		payload.update(overrides)
		return call_api(questions.create_question, **payload)

	def question_count(self):
		return frappe.db.count("Assessment Question", {"assessment": self.assessment.name})

	def test_same_key_and_payload_returns_the_original_question(self):
		first, first_response = self.create()
		second, second_response = self.create()

		self.assertNotIn("errors", first_response, first_response)
		self.assertNotIn("errors", second_response, second_response)
		self.assertEqual(first, second)
		self.assertEqual(self.question_count(), 1)

	def test_same_key_with_a_different_payload_is_a_conflict(self):
		self.create()
		result, response = self.create(content="<p>A different question</p>")

		self.assertIsNone(result)
		self.assertEqual(response.get("http_status_code"), 409)
		self.assertEqual(response["errors"][0]["code"], "IDEMPOTENCY_KEY_REUSED")
		self.assertEqual(self.question_count(), 1)

	def test_keys_are_scoped_per_user(self):
		first, _ = self.create(user=MANAGER)
		second, _ = self.create(user=OTHER_MANAGER)

		self.assertNotEqual(first["id"], second["id"])
		self.assertEqual(self.question_count(), 2)

	def test_without_a_key_every_call_creates_a_question(self):
		self.create(idempotency_key=None)
		self.create(idempotency_key=None)
		self.assertEqual(self.question_count(), 2)

	def test_key_longer_than_64_characters_is_rejected(self):
		_, response = self.create(idempotency_key="k" * 65)
		self.assertEqual(response.get("http_status_code"), 400)
		self.assertEqual(response["errors"][0]["code"], "INVALID_PARAMETER")
		self.assertEqual(self.question_count(), 0)

	def test_replay_still_works_after_the_assessment_was_archived(self):
		first, _ = self.create()
		frappe.set_user("Administrator")
		self.assessment.reload()
		self.assessment.archive()

		second, response = self.create()

		self.assertNotIn("errors", response, response)
		self.assertEqual(first, second)

	def test_concurrent_duplicate_is_resolved_by_the_unique_index(self):
		"""Two identical requests race: both miss the lookup, the DB unique index rejects the second."""
		first, _ = self.create()
		calls = []

		def lookup_misses_once(key_hash):
			calls.append(key_hash)
			return None if len(calls) == 1 else find_existing(key_hash)

		with patch("assessment_hub.api.v1.questions.find_existing", side_effect=lookup_misses_once):
			second, response = self.create()

		self.assertNotIn("errors", response, response)
		self.assertEqual(first, second)
		self.assertEqual(self.question_count(), 1)
		self.assertEqual(len(calls), 2)
