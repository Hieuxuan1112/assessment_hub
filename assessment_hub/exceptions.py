import frappe


class InvalidStateError(frappe.ValidationError):
	"""The operation is not allowed in the document's current state (e.g. Archived)."""

	http_status_code = 409


class ApiParameterError(frappe.ValidationError):
	"""A Partner API request parameter is missing or invalid."""

	http_status_code = 400

	def __init__(self, message: str, code: str = "INVALID_PARAMETER"):
		super().__init__(message)
		self.code = code
