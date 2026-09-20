import frappe

SETTINGS_DOCTYPE = "Assessment Hub Settings"

DEFAULT_SETTINGS = {
	"default_page_length": 20,
	"max_page_length": 100,
	"api_rate_limit_per_minute": 120,
	"min_answers_per_question": 1,
	"allow_publish_without_questions": 0,
}


def get_settings() -> frappe._dict:
	"""Return Assessment Hub Settings, falling back to safe defaults for unset page lengths."""
	doc = frappe.get_cached_doc(SETTINGS_DOCTYPE)
	values = frappe._dict()
	for key, default in DEFAULT_SETTINGS.items():
		value = doc.get(key)
		values[key] = default if value is None else value
	if not values.default_page_length or values.default_page_length < 1:
		values.default_page_length = DEFAULT_SETTINGS["default_page_length"]
	if not values.max_page_length or values.max_page_length < values.default_page_length:
		values.max_page_length = max(DEFAULT_SETTINGS["max_page_length"], values.default_page_length)
	return values
