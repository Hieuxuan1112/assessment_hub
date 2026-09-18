# Copyright (c) 2026, Ngo Xuan Hieu and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import escape_html

from assessment_hub.exceptions import InvalidStateError
from assessment_hub.utils.settings import get_settings

# previous status -> statuses it may be saved with
ALLOWED_TRANSITIONS = {
	"Draft": {"Draft", "Published", "Archived"},
	"Published": {"Published", "Archived"},
	"Archived": set(),
}


class Assessment(Document):
	def validate(self):
		self.title = (self.title or "").strip()
		self.validate_status_transition()
		if self.status == "Published" and self.has_value_changed("status"):
			self.validate_can_publish()

	def validate_status_transition(self):
		previous = self.get_doc_before_save()
		if previous is None:
			if self.status != "Draft":
				frappe.throw(_("A new Assessment must start in Draft status."), InvalidStateError)
			return

		if previous.status == "Archived":
			frappe.throw(
				_("Assessment {0} is archived and can no longer be modified.").format(
					frappe.bold(escape_html(self.name))
				),
				InvalidStateError,
			)

		if self.status not in ALLOWED_TRANSITIONS.get(previous.status, set()):
			frappe.throw(
				_("Cannot change status from {0} to {1}.").format(
					frappe.bold(_(previous.status)), frappe.bold(escape_html(self.status or ""))
				),
				InvalidStateError,
			)

	def validate_can_publish(self):
		if get_settings().allow_publish_without_questions:
			return
		if not frappe.db.exists("Assessment Question", {"assessment": self.name, "status": "Active"}):
			frappe.throw(
				_("Add at least one active question before publishing this Assessment."),
				InvalidStateError,
			)

	@frappe.whitelist()
	def publish(self):
		self.status = "Published"
		self.save()
		return self.status

	@frappe.whitelist()
	def archive(self):
		self.status = "Archived"
		self.save()
		return self.status
