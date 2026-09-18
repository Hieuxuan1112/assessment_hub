import frappe
from frappe.model.document import Document

from assessment_hub.utils.settings import SETTINGS_DOCTYPE

DEFAULT_ANSWERS = (
	{"content": "4", "score": 1},
	{"content": "5", "score": 0},
)


def make_assessment(title: str = "Test Assessment", status: str = "Draft", **values) -> Document:
	"""Insert an Assessment and move it to `status` through the allowed transitions."""
	doc = frappe.get_doc({"doctype": "Assessment", "title": title, **values})
	doc.insert()
	if status == "Published":
		make_question(doc.name)
	if status in ("Published", "Archived"):
		doc.reload()
		doc.status = status
		doc.save()
	return doc


def make_question(
	assessment: str, content: str = "<p>What is 2 + 2?</p>", answers=None, **values
) -> Document:
	rows = DEFAULT_ANSWERS if answers is None else answers
	doc = frappe.get_doc(
		{
			"doctype": "Assessment Question",
			"assessment": assessment,
			"content": content,
			"answers": [dict(row) for row in rows],
			**values,
		}
	)
	doc.insert()
	return doc


def make_user(email: str, roles: tuple[str, ...]) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
				"roles": [{"role": role} for role in roles],
			}
		).insert(ignore_permissions=True)
	return email


def call_api(fn, **kwargs):
	"""Call an API function the way the HTTP layer does; return (return_value, frappe.local.response)."""
	frappe.local.response = frappe._dict()
	frappe.local.message_log = []
	result = fn(**kwargs)
	return result, frappe.local.response


def override_settings(test_case, **values):
	"""Change Assessment Hub Settings for one test and restore them afterwards (cache-safe)."""
	settings = frappe.get_single(SETTINGS_DOCTYPE)
	previous = {key: settings.get(key) for key in values}
	settings.update(values)
	settings.save()

	def restore():
		doc = frappe.get_single(SETTINGS_DOCTYPE)
		doc.update(previous)
		doc.save()

	test_case.addCleanup(restore)
