"""Response envelope for the Partner API.

Success: the endpoint's return value -> Frappe v2 puts it in {"data": ...}.
Failure: {"errors": [{"message": str, "code": str}]} with a matching HTTP status.
Every call runs inside a database savepoint that is rolled back on any error,
so a failed request never leaves partial writes behind.
"""

import functools
import html

import frappe
from frappe import _
from frappe.utils import strip_html_tags

from assessment_hub.exceptions import ApiParameterError, InvalidStateError

DEFAULT_MESSAGES = {
	"PERMISSION_DENIED": "You do not have permission to perform this action.",
	"NOT_FOUND": "The requested resource was not found.",
	"INVALID_STATE": "The resource is not in a state that allows this action.",
	"VALIDATION_ERROR": "The request could not be validated.",
	"INVALID_PARAMETER": "A request parameter is invalid.",
	"MISSING_PARAMETER": "A required request parameter is missing.",
}


def _clean_message(exc: BaseException) -> str:
	return html.unescape(strip_html_tags(str(exc))).strip()


def _classify(exc: BaseException) -> tuple[int, str] | None:
	# Order matters: specific subclasses of ValidationError come first.
	if isinstance(exc, ApiParameterError):
		return 400, exc.code
	if isinstance(exc, frappe.PermissionError):
		return 403, "PERMISSION_DENIED"
	if isinstance(exc, frappe.DoesNotExistError):
		return 404, "NOT_FOUND"
	if isinstance(exc, InvalidStateError):
		return 409, "INVALID_STATE"
	if isinstance(exc, frappe.ValidationError):
		return 422, "VALIDATION_ERROR"
	return None


def _set_error(status: int, code: str, message: str) -> None:
	frappe.local.response["http_status_code"] = status
	frappe.local.response["errors"] = [{"message": message, "code": code}]


def api_endpoint(fn):
	"""Wrap a whitelisted API function with savepoint rollback and the error envelope."""

	@functools.wraps(fn)
	def wrapper(*args, **kwargs):
		savepoint = f"ah_api_{frappe.generate_hash(length=10)}"
		frappe.db.savepoint(savepoint)
		try:
			result = fn(*args, **kwargs)
		except Exception as exc:
			frappe.db.rollback(save_point=savepoint)
			frappe.local.message_log = []

			classified = _classify(exc)
			if classified is None:
				error_log = frappe.log_error(title=f"Assessment Hub API error in {fn.__name__}")
				frappe.local.flags.commit = True  # keep the Error Log row even for GET requests
				reference = getattr(error_log, "name", None)
				message = _("Unexpected server error.")
				if reference:
					message = _("Unexpected server error. Reference: {0}").format(reference)
				_set_error(500, "INTERNAL_ERROR", message)
				return None

			status, code = classified
			_set_error(status, code, _clean_message(exc) or DEFAULT_MESSAGES[code])
			return None

		frappe.db.release_savepoint(savepoint)
		return result

	return wrapper
