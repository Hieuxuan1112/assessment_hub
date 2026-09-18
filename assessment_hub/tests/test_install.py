import frappe
from frappe.tests import IntegrationTestCase

from assessment_hub.install import ROLES, ensure_default_settings, ensure_roles
from assessment_hub.utils.settings import DEFAULT_SETTINGS, SETTINGS_DOCTYPE, get_settings


class TestInstall(IntegrationTestCase):
	def test_roles_exist_with_desk_access(self):
		for role in ROLES:
			with self.subTest(role=role):
				self.assertTrue(frappe.db.exists("Role", role))
				self.assertEqual(frappe.db.get_value("Role", role, "desk_access"), 1)

	def test_ensure_roles_is_idempotent(self):
		ensure_roles()
		ensure_roles()
		for role in ROLES:
			self.assertEqual(frappe.db.count("Role", {"name": role}), 1)

	def test_default_settings_are_stored(self):
		settings = get_settings()
		for key, value in DEFAULT_SETTINGS.items():
			with self.subTest(key=key):
				self.assertEqual(settings[key], value)

	def test_ensure_default_settings_keeps_existing_values(self):
		settings = frappe.get_single(SETTINGS_DOCTYPE)
		original = settings.default_page_length
		self.addCleanup(self._restore_setting, "default_page_length", original)
		settings.default_page_length = 7
		settings.save()

		ensure_default_settings()

		self.assertEqual(frappe.get_single(SETTINGS_DOCTYPE).default_page_length, 7)

	def _restore_setting(self, key, value):
		doc = frappe.get_single(SETTINGS_DOCTYPE)
		doc.set(key, value)
		doc.save()
