# Copyright (c) 2026, Ngo Xuan Hieu and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

MAX_PAGE_LENGTH_LIMIT = 500


class AssessmentHubSettings(Document):
	def validate(self):
		if (self.default_page_length or 0) < 1:
			frappe.throw(_("Default Page Length must be at least 1."))
		if (self.max_page_length or 0) < self.default_page_length:
			frappe.throw(_("Max Page Length must be greater than or equal to Default Page Length."))
		if self.max_page_length > MAX_PAGE_LENGTH_LIMIT:
			frappe.throw(_("Max Page Length cannot exceed {0}.").format(MAX_PAGE_LENGTH_LIMIT))
		if (self.min_answers_per_question or 0) < 0:
			frappe.throw(_("Min Answers per Question cannot be negative."))
