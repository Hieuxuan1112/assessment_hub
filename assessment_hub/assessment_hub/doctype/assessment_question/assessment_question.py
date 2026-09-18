# Copyright (c) 2026, Ngo Xuan Hieu and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Max
from frappe.utils import cint, escape_html, flt

from assessment_hub.exceptions import InvalidStateError
from assessment_hub.utils.settings import get_settings


class AssessmentQuestion(Document):
	def validate(self):
		self.validate_assessment_is_open()
		self.validate_sort_order()
		self.validate_answers()

	def validate_assessment_is_open(self):
		if not self.assessment:
			return  # the mandatory-field check reports a missing assessment

		status = frappe.db.get_value("Assessment", self.assessment, "status")
		if status is None:
			frappe.throw(
				_("Assessment {0} does not exist.").format(frappe.bold(escape_html(self.assessment))),
				frappe.DoesNotExistError,
			)
		if status == "Archived":
			frappe.throw(
				_("Assessment {0} is archived; its questions cannot be added or changed.").format(
					frappe.bold(escape_html(self.assessment))
				),
				InvalidStateError,
			)

		previous = self.get_doc_before_save()
		if previous and previous.assessment != self.assessment:
			if frappe.db.get_value("Assessment", previous.assessment, "status") == "Archived":
				frappe.throw(
					_("This question belongs to archived Assessment {0} and cannot be moved.").format(
						frappe.bold(escape_html(previous.assessment))
					),
					InvalidStateError,
				)

	def validate_sort_order(self):
		if cint(self.sort_order) == 0:
			self.sort_order = self.next_sort_order()
		elif cint(self.sort_order) < 0:
			frappe.throw(_("Sort Order cannot be negative."))

	def next_sort_order(self) -> int:
		question = frappe.qb.DocType("Assessment Question")
		query = (
			frappe.qb.from_(question)
			.select(Max(question.sort_order))
			.where(question.assessment == self.assessment)
		)
		if not self.is_new():
			query = query.where(question.name != self.name)
		current = query.run()[0][0]
		return cint(current) + 1

	def validate_answers(self):
		minimum = cint(get_settings().min_answers_per_question)
		if len(self.answers) < minimum:
			frappe.throw(_("A question needs at least {0} answer(s).").format(minimum))

		seen = set()
		for position, answer in enumerate(self.answers, start=1):
			answer.content = (answer.content or "").strip()
			if not answer.content:
				frappe.throw(_("Answer #{0}: content is required.").format(position))
			if flt(answer.score) < 0:
				frappe.throw(_("Answer #{0}: score cannot be negative.").format(position))

			key = answer.content.casefold()
			if key in seen:
				frappe.throw(
					_("Answer #{0}: duplicate answer {1}.").format(
						position, frappe.bold(escape_html(answer.content))
					)
				)
			seen.add(key)

			if cint(answer.sort_order) == 0:
				answer.sort_order = position
			elif cint(answer.sort_order) < 0:
				frappe.throw(_("Answer #{0}: sort order cannot be negative.").format(position))


def on_doctype_update():
	"""Called by Frappe after this DocType's table is synced."""
	frappe.db.add_index("Assessment Question", ["assessment", "sort_order"])
