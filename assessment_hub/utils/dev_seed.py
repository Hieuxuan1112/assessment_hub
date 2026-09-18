"""Development/CI helpers. Refuse to run on production sites.

bench --site assessment.localhost execute assessment_hub.utils.dev_seed.create_sample_content
"""

import frappe

SAMPLE_CONTENT = [
	(
		"Python Fundamentals",
		"Published",
		[
			(
				"<p>Which keyword defines a function in Python?</p>",
				[("def", 1), ("func", 0), ("lambda only", 0)],
			),
			("<p>What does <code>len([1, 2, 3])</code> return?</p>", [("3", 1), ("2", 0)]),
		],
	),
	(
		"Frappe Framework Basics",
		"Draft",
		[("<p>Which file registers document event hooks?</p>", [("hooks.py", 1), ("setup.py", 0)])],
	),
	(
		"Legacy SQL Quiz",
		"Archived",
		[("<p>Which clause filters grouped rows?</p>", [("HAVING", 1), ("WHERE", 0)])],
	),
	(
		'XSS probe <img src=x onerror="alert(1)">',
		"Draft",
		[
			(
				'<p>Probe</p><img src=x onerror="alert(2)"><script>alert(3)</script>',
				[("<b>bold?</b>", 1), ("plain", 0)],
			)
		],
	),
]


def ensure_dev_site():
	if not (frappe.conf.developer_mode or frappe.conf.allow_tests):
		frappe.throw("dev_seed only runs on sites with developer_mode or allow_tests enabled.")


def create_sample_content() -> list[str]:
	ensure_dev_site()
	created = []
	for title, status, questions in SAMPLE_CONTENT:
		if frappe.db.exists("Assessment", {"title": frappe.utils.sanitize_html(title)}):
			continue
		assessment = frappe.get_doc(
			{"doctype": "Assessment", "title": title, "description": f"Sample assessment ({status})"}
		).insert()
		for content, answers in questions:
			frappe.get_doc(
				{
					"doctype": "Assessment Question",
					"assessment": assessment.name,
					"content": content,
					"answers": [{"content": text, "score": score} for text, score in answers],
				}
			).insert()
		if status != "Draft":
			assessment.reload()
			assessment.status = status
			assessment.save()
		created.append(assessment.name)
	return created


API_USERS = {
	"manager": ("ah.api.manager@example.com", "Assessment Manager"),
	"viewer": ("ah.api.viewer@example.com", "Assessment Viewer"),
}


def create_api_users(output_path: str = "/tmp/assessment_hub_tokens.env") -> str:
	"""Create Manager/Viewer API users with fresh token credentials.

	Credentials are written to `output_path` (outside the repo) as
	MANAGER_TOKEN=<api_key>:<api_secret> and VIEWER_TOKEN=... lines. Never commit that file.
	"""
	ensure_dev_site()
	lines = []
	for key, (email, role) in API_USERS.items():
		if frappe.db.exists("User", email):
			user = frappe.get_doc("User", email)
		else:
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": f"API {key.title()}",
					"send_welcome_email": 0,
					"roles": [{"role": role}],
				}
			)
			user.insert(ignore_permissions=True)
		api_secret = frappe.generate_hash(length=15)
		user.api_key = user.api_key or frappe.generate_hash(length=15)
		user.api_secret = api_secret
		user.save(ignore_permissions=True)
		lines.append(f"{key.upper()}_TOKEN={user.api_key}:{api_secret}")

	with open(output_path, "w", encoding="utf-8") as handle:
		handle.write("\n".join(lines) + "\n")
	return output_path
