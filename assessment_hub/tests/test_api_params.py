from frappe.tests import IntegrationTestCase

from assessment_hub.api.v1._params import (
	escape_like,
	optional_str,
	parse_answers,
	parse_bool,
	parse_choice,
	parse_datetime,
	parse_int,
	parse_number,
	parse_pagination,
	require_str,
	split_page,
)
from assessment_hub.exceptions import ApiParameterError
from assessment_hub.tests.utils import override_settings


class TestApiParams(IntegrationTestCase):
	def assertParamError(self, code, fn, *args, **kwargs):
		with self.assertRaises(ApiParameterError) as ctx:
			fn(*args, **kwargs)
		self.assertEqual(ctx.exception.code, code)
		return ctx.exception

	def test_require_str(self):
		self.assertEqual(require_str("  ASM-00001 ", "id"), "ASM-00001")
		self.assertParamError("MISSING_PARAMETER", require_str, None, "id")
		self.assertParamError("MISSING_PARAMETER", require_str, "   ", "id")
		self.assertParamError("INVALID_PARAMETER", require_str, 12, "id")
		self.assertParamError("INVALID_PARAMETER", require_str, "x" * 141, "id")

	def test_optional_str(self):
		self.assertIsNone(optional_str("", "search"))
		self.assertEqual(optional_str(" quiz ", "search"), "quiz")

	def test_parse_choice(self):
		self.assertEqual(parse_choice("Draft", "status", ("Draft", "Published")), "Draft")
		self.assertIsNone(parse_choice(None, "status", ("Draft",)))
		self.assertParamError("INVALID_PARAMETER", parse_choice, "draft", "status", ("Draft",))

	def test_parse_bool(self):
		for value in ("1", "true", "YES", 1, True):
			self.assertTrue(parse_bool(value, "flag"))
		for value in ("0", "false", "no", 0, False):
			self.assertFalse(parse_bool(value, "flag"))
		self.assertTrue(parse_bool(None, "flag", default=True))
		self.assertParamError("INVALID_PARAMETER", parse_bool, "maybe", "flag")

	def test_parse_int(self):
		self.assertEqual(parse_int("20", "page_length"), 20)
		self.assertEqual(parse_int(" -3 ", "n"), -3)
		self.assertEqual(parse_int(None, "n", default=5), 5)
		self.assertParamError("INVALID_PARAMETER", parse_int, "--5", "n")
		self.assertParamError("INVALID_PARAMETER", parse_int, "1.5", "n")
		self.assertParamError("INVALID_PARAMETER", parse_int, True, "n")
		self.assertParamError("INVALID_PARAMETER", parse_int, "0", "n", minimum=1)
		self.assertParamError("INVALID_PARAMETER", parse_int, "101", "n", maximum=100)

	def test_parse_number(self):
		self.assertEqual(parse_number("2.5", "score"), 2.5)
		self.assertEqual(parse_number(3, "score"), 3.0)
		self.assertParamError("MISSING_PARAMETER", parse_number, None, "score")
		self.assertParamError("INVALID_PARAMETER", parse_number, "abc", "score")
		self.assertParamError("INVALID_PARAMETER", parse_number, "nan", "score")
		self.assertParamError("INVALID_PARAMETER", parse_number, True, "score")

	def test_parse_datetime(self):
		self.assertEqual(parse_datetime("2026-09-17 08:30:00", "updated_since").hour, 8)
		self.assertIsNone(parse_datetime(None, "updated_since"))
		self.assertParamError("INVALID_PARAMETER", parse_datetime, "not-a-date", "updated_since")

	def test_parse_pagination_defaults_and_page(self):
		override_settings(self, default_page_length=20, max_page_length=100)
		self.assertEqual(parse_pagination(None, None, None), (0, 20))
		self.assertEqual(parse_pagination("10", "30", None), (30, 10))
		self.assertEqual(parse_pagination("10", None, "3"), (20, 10))
		self.assertParamError("INVALID_PARAMETER", parse_pagination, "10", "0", "1")
		self.assertParamError("INVALID_PARAMETER", parse_pagination, "101", None, None)
		self.assertParamError("INVALID_PARAMETER", parse_pagination, None, None, "0")

	def test_split_page(self):
		rows, meta = split_page([1, 2, 3], offset=10, length=2)
		self.assertEqual(rows, [1, 2])
		self.assertEqual(meta, {"start": 10, "page_length": 2, "has_more": True, "next_start": 12})
		rows, meta = split_page([1], offset=0, length=2)
		self.assertEqual(meta["has_more"], False)
		self.assertIsNone(meta["next_start"])

	def test_escape_like(self):
		self.assertEqual(escape_like("100%_a\\b"), "100\\%\\_a\\\\b")

	def test_parse_answers(self):
		rows = parse_answers(
			'[{"content": " Yes ", "score": "1"}, {"content": "No", "score": 0, "sort_order": 2}]'
		)
		self.assertEqual(
			rows,
			[
				{"content": "Yes", "score": 1.0, "sort_order": None},
				{"content": "No", "score": 0.0, "sort_order": 2},
			],
		)
		self.assertParamError("MISSING_PARAMETER", parse_answers, None)
		self.assertParamError("INVALID_PARAMETER", parse_answers, "not json")
		self.assertParamError("INVALID_PARAMETER", parse_answers, [])
		self.assertParamError("INVALID_PARAMETER", parse_answers, ["text"])
		error = self.assertParamError("INVALID_PARAMETER", parse_answers, [{"content": "A", "score": "x"}])
		self.assertIn("answers[0].score", str(error))
		self.assertParamError("INVALID_PARAMETER", parse_answers, [{"content": "A", "score": 1}] * 51)
