import frappe

from assessment_hub.api.v1._serializers import serialize_answer

QUESTION_DOCTYPE = "Assessment Question"
QUESTION_FIELDS = ["name", "assessment", "content", "sort_order", "status", "creation", "modified"]
QUESTION_ORDER = "sort_order asc, creation asc, name asc"


def fetch_questions(
	assessment_id: str, *, status: str | None = None, start: int = 0, page_length: int = 0
) -> list:
	"""Questions of one assessment. frappe.get_list enforces the caller's read permission."""
	filters = {"assessment": assessment_id}
	if status:
		filters["status"] = status
	return frappe.get_list(
		QUESTION_DOCTYPE,
		filters=filters,
		fields=QUESTION_FIELDS,
		order_by=QUESTION_ORDER,
		limit_start=start,
		limit_page_length=page_length,
	)


def fetch_answers_by_question(question_names: list[str]) -> dict[str, list[dict]]:
	"""Answers for many questions in ONE query (no N+1).

	Only pass names returned by fetch_questions or by a permission-checked document:
	child rows carry no permissions of their own, so access was already decided on the parent.
	"""
	grouped = {name: [] for name in question_names}
	if not question_names:
		return grouped
	rows = frappe.get_all(
		"Assessment Answer",
		filters={
			"parenttype": QUESTION_DOCTYPE,
			"parentfield": "answers",
			"parent": ["in", question_names],
		},
		fields=["name", "parent", "content", "score", "sort_order", "idx"],
		order_by="parent asc, sort_order asc, idx asc",
	)
	for row in rows:
		grouped[row.parent].append(serialize_answer(row))
	return grouped
