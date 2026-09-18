"""Partner API: assessments.

GET /api/v2/method/assessment_hub.api.v1.assessments.list_assessments
GET /api/v2/method/assessment_hub.api.v1.assessments.get_assessment
"""

from typing import Any

import frappe

from assessment_hub.api.v1._params import (
	escape_like,
	optional_str,
	parse_bool,
	parse_choice,
	parse_datetime,
	parse_pagination,
	require_str,
	split_page,
)
from assessment_hub.api.v1._queries import fetch_answers_by_question, fetch_questions
from assessment_hub.api.v1._response import api_endpoint
from assessment_hub.api.v1._serializers import serialize_assessment, serialize_question

ASSESSMENT_DOCTYPE = "Assessment"
ASSESSMENT_FIELDS = ["name", "title", "description", "status", "creation", "modified"]
ASSESSMENT_STATUSES = ("Draft", "Published", "Archived")


@frappe.whitelist(methods=["GET"])
@api_endpoint
def list_assessments(
	status: Any = None,
	search: Any = None,
	updated_since: Any = None,
	page_length: Any = None,
	start: Any = None,
	page: Any = None,
) -> dict:
	"""List assessments. With `updated_since`, results are ordered oldest-change first for incremental sync."""
	frappe.has_permission(ASSESSMENT_DOCTYPE, "read", throw=True)
	offset, length = parse_pagination(page_length, start, page)

	filters = []
	if status_value := parse_choice(status, "status", ASSESSMENT_STATUSES):
		filters.append(["status", "=", status_value])
	if search_value := optional_str(search, "search"):
		filters.append(["title", "like", f"%{escape_like(search_value)}%"])
	since = parse_datetime(updated_since, "updated_since")
	if since:
		filters.append(["modified", ">=", since])

	rows = frappe.get_list(
		ASSESSMENT_DOCTYPE,
		filters=filters,
		fields=ASSESSMENT_FIELDS,
		order_by="modified asc, name asc" if since else "modified desc, name desc",
		limit_start=offset,
		limit_page_length=length + 1,
	)
	rows, pagination = split_page(rows, offset, length)
	return {"items": [serialize_assessment(row) for row in rows], "pagination": pagination}


@frappe.whitelist(methods=["GET"])
@api_endpoint
def get_assessment(id: Any = None, include_questions: Any = None) -> dict:
	"""One assessment; with include_questions=1 also its questions and their answers (2 extra queries total)."""
	frappe.has_permission(ASSESSMENT_DOCTYPE, "read", throw=True)
	assessment_id = require_str(id, "id")
	with_questions = parse_bool(include_questions, "include_questions")

	doc = frappe.get_doc(ASSESSMENT_DOCTYPE, assessment_id)
	doc.check_permission("read")
	data = serialize_assessment(doc)

	if with_questions:
		questions = fetch_questions(doc.name)
		answers = fetch_answers_by_question([question.name for question in questions])
		data["questions"] = [serialize_question(question, answers[question.name]) for question in questions]
	return data
