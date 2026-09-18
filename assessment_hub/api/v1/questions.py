"""Partner API: questions.

GET  /api/v2/method/assessment_hub.api.v1.questions.list_questions
POST /api/v2/method/assessment_hub.api.v1.questions.create_question
"""

from typing import Any

import frappe
from frappe import _

from assessment_hub.api.v1._params import (
	parse_answers,
	parse_bool,
	parse_choice,
	parse_int,
	parse_pagination,
	require_str,
	split_page,
)
from assessment_hub.api.v1._queries import QUESTION_DOCTYPE, fetch_answers_by_question, fetch_questions
from assessment_hub.api.v1._response import api_endpoint
from assessment_hub.api.v1._serializers import serialize_answer, serialize_question

QUESTION_STATUSES = ("Active", "Inactive")


def _get_readable_assessment(assessment_id: str) -> None:
	if not frappe.db.exists("Assessment", assessment_id):
		raise frappe.DoesNotExistError(_("Assessment {0} not found.").format(assessment_id))
	frappe.has_permission("Assessment", "read", doc=assessment_id, throw=True)


@frappe.whitelist(methods=["GET"])
@api_endpoint
def list_questions(
	assessment_id: Any = None,
	status: Any = None,
	include_answers: Any = None,
	page_length: Any = None,
	start: Any = None,
	page: Any = None,
) -> dict:
	"""Questions of one assessment ordered by sort_order ascending."""
	frappe.has_permission(QUESTION_DOCTYPE, "read", throw=True)
	assessment = require_str(assessment_id, "assessment_id")
	status_value = parse_choice(status, "status", QUESTION_STATUSES)
	with_answers = parse_bool(include_answers, "include_answers")
	offset, length = parse_pagination(page_length, start, page)
	_get_readable_assessment(assessment)

	rows = fetch_questions(assessment, status=status_value, start=offset, page_length=length + 1)
	rows, pagination = split_page(rows, offset, length)
	answers = fetch_answers_by_question([row.name for row in rows]) if with_answers else {}
	return {
		"items": [serialize_question(row, answers[row.name] if with_answers else None) for row in rows],
		"pagination": pagination,
	}


@frappe.whitelist(methods=["POST"])
@api_endpoint
def create_question(
	assessment_id: Any = None,
	content: Any = None,
	sort_order: Any = None,
	status: Any = None,
	answers: Any = None,
) -> dict:
	"""Create a question with all its answers atomically.

	Parent and child rows are written by a single doc.insert(). The api_endpoint decorator
	wraps the call in a savepoint, so any failure (validation, permission, or a crash after
	the rows were written) rolls back the question and every answer together.
	"""
	frappe.has_permission(QUESTION_DOCTYPE, "create", throw=True)
	assessment = require_str(assessment_id, "assessment_id")
	question_content = require_str(content, "content", max_length=10000)
	order = parse_int(sort_order, "sort_order", minimum=1)
	status_value = parse_choice(status, "status", QUESTION_STATUSES) or "Active"
	answer_rows = parse_answers(answers)
	_get_readable_assessment(assessment)

	question = frappe.get_doc(
		{
			"doctype": QUESTION_DOCTYPE,
			"assessment": assessment,
			"content": question_content,
			"sort_order": order,
			"status": status_value,
			"answers": answer_rows,
		}
	)
	question.insert()

	ordered_answers = sorted(question.answers, key=lambda row: (row.sort_order, row.idx))
	return serialize_question(question, [serialize_answer(row) for row in ordered_answers])
