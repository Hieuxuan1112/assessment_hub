from frappe.utils import cint, flt, get_datetime


def _iso(value) -> str | None:
	return get_datetime(value).isoformat() if value else None


def serialize_assessment(row) -> dict:
	return {
		"id": row.name,
		"title": row.title,
		"description": row.description,
		"status": row.status,
		"created_at": _iso(row.creation),
		"updated_at": _iso(row.modified),
	}


def serialize_answer(row) -> dict:
	return {
		"id": row.name,
		"content": row.content,
		"score": flt(row.score),
		"sort_order": cint(row.sort_order),
	}


def serialize_question(row, answers: list[dict] | None = None) -> dict:
	data = {
		"id": row.name,
		"assessment_id": row.assessment,
		"content": row.content,
		"sort_order": cint(row.sort_order),
		"status": row.status,
		"created_at": _iso(row.creation),
		"updated_at": _iso(row.modified),
	}
	if answers is not None:
		data["answers"] = answers
	return data
