"""Strict parsing of Partner API request parameters.

Query-string values arrive as strings; JSON bodies may carry ints, floats, bools and lists.
Every helper raises ApiParameterError (HTTP 400) with a precise, partner-readable message.
"""

import json
import math
import re
from typing import Any

from frappe import _
from frappe.utils import get_datetime

from assessment_hub.exceptions import ApiParameterError
from assessment_hub.utils.settings import get_settings

TRUE_VALUES = {"1", "true", "yes"}
FALSE_VALUES = {"0", "false", "no"}
INTEGER_PATTERN = re.compile(r"-?\d+")
MAX_ANSWERS = 50


def _is_blank(value: Any) -> bool:
	return value is None or (isinstance(value, str) and not value.strip())


def _missing(name: str) -> ApiParameterError:
	return ApiParameterError(_("Parameter '{0}' is required.").format(name), "MISSING_PARAMETER")


def _invalid(name: str, requirement: str) -> ApiParameterError:
	return ApiParameterError(_("Parameter '{0}' {1}.").format(name, requirement), "INVALID_PARAMETER")


def require_str(value: Any, name: str, *, max_length: int = 140) -> str:
	if _is_blank(value):
		raise _missing(name)
	if not isinstance(value, str):
		raise _invalid(name, "must be a string")
	value = value.strip()
	if len(value) > max_length:
		raise _invalid(name, f"must be at most {max_length} characters")
	return value


def optional_str(value: Any, name: str, *, max_length: int = 140) -> str | None:
	if _is_blank(value):
		return None
	return require_str(value, name, max_length=max_length)


def parse_choice(value: Any, name: str, choices: tuple[str, ...]) -> str | None:
	text = optional_str(value, name)
	if text is None:
		return None
	if text not in choices:
		raise _invalid(name, "must be one of: " + ", ".join(choices))
	return text


def parse_bool(value: Any, name: str, *, default: bool = False) -> bool:
	if _is_blank(value):
		return default
	if isinstance(value, bool):
		return value
	if isinstance(value, int) and value in (0, 1):
		return bool(value)
	if isinstance(value, str):
		lowered = value.strip().lower()
		if lowered in TRUE_VALUES:
			return True
		if lowered in FALSE_VALUES:
			return False
	raise _invalid(name, "must be one of 1, 0, true, false")


def parse_int(
	value: Any,
	name: str,
	*,
	default: int | None = None,
	minimum: int | None = None,
	maximum: int | None = None,
) -> int | None:
	if _is_blank(value):
		return default
	if isinstance(value, bool):
		raise _invalid(name, "must be an integer")
	if isinstance(value, int):
		parsed = value
	elif isinstance(value, str) and INTEGER_PATTERN.fullmatch(value.strip()):
		parsed = int(value.strip())
	else:
		raise _invalid(name, "must be an integer")
	if minimum is not None and parsed < minimum:
		raise _invalid(name, f"must be >= {minimum}")
	if maximum is not None and parsed > maximum:
		raise _invalid(name, f"must be <= {maximum}")
	return parsed


def parse_number(value: Any, name: str) -> float:
	if _is_blank(value):
		raise _missing(name)
	if isinstance(value, bool):
		raise _invalid(name, "must be a number")
	if isinstance(value, int | float):
		parsed = float(value)
	elif isinstance(value, str):
		try:
			parsed = float(value.strip())
		except ValueError:
			raise _invalid(name, "must be a number") from None
	else:
		raise _invalid(name, "must be a number")
	if not math.isfinite(parsed):
		raise _invalid(name, "must be a finite number")
	return parsed


def parse_datetime(value: Any, name: str):
	text = optional_str(value, name, max_length=40)
	if text is None:
		return None
	try:
		return get_datetime(text)
	except Exception:
		raise _invalid(name, "must be a datetime such as 2026-09-17 08:30:00") from None


def parse_pagination(page_length: Any, start: Any, page: Any) -> tuple[int, int]:
	"""Return (offset, length). Partners send either `start` (offset) or `page` (1-based)."""
	settings = get_settings()
	length = parse_int(
		page_length,
		"page_length",
		default=settings.default_page_length,
		minimum=1,
		maximum=settings.max_page_length,
	)
	if not _is_blank(start) and not _is_blank(page):
		raise ApiParameterError(_("Use either 'start' or 'page', not both."), "INVALID_PARAMETER")
	if not _is_blank(page):
		return (parse_int(page, "page", minimum=1) - 1) * length, length
	return parse_int(start, "start", default=0, minimum=0), length


def split_page(rows: list, offset: int, length: int) -> tuple[list, dict]:
	"""`rows` must be fetched with limit length + 1; the extra row only signals has_more."""
	has_more = len(rows) > length
	return rows[:length], {
		"start": offset,
		"page_length": length,
		"has_more": has_more,
		"next_start": offset + length if has_more else None,
	}


def escape_like(value: str) -> str:
	return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def parse_answers(value: Any) -> list[dict]:
	if value is None or (isinstance(value, str) and not value.strip()):
		raise _missing("answers")
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except ValueError:
			raise _invalid("answers", "must be a JSON array") from None
	if not isinstance(value, list) or not value:
		raise _invalid("answers", "must be a non-empty array")
	if len(value) > MAX_ANSWERS:
		raise _invalid("answers", f"must contain at most {MAX_ANSWERS} items")

	rows = []
	for index, item in enumerate(value):
		label = f"answers[{index}]"
		if not isinstance(item, dict):
			raise _invalid(label, "must be an object")
		rows.append(
			{
				"content": require_str(item.get("content"), f"{label}.content", max_length=1000),
				"score": parse_number(item.get("score"), f"{label}.score"),
				"sort_order": parse_int(item.get("sort_order"), f"{label}.sort_order", minimum=1),
			}
		)
	return rows
