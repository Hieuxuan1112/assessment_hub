import click
import frappe

from assessment_hub.utils.settings import DEFAULT_SETTINGS, SETTINGS_DOCTYPE

ROLES = ("Assessment Manager", "Assessment Viewer")


def after_install():
	"""Runs after DocTypes are synced but BEFORE fixtures are synced (see frappe/installer.py)."""
	ensure_roles()
	ensure_default_settings()


def before_uninstall():
	remove_roles()
	remove_app_level_records()


def ensure_roles():
	for role_name in ROLES:
		if frappe.db.exists("Role", role_name):
			if not frappe.db.get_value("Role", role_name, "desk_access"):
				frappe.db.set_value("Role", role_name, "desk_access", 1)
			continue
		role = frappe.new_doc("Role")
		role.role_name = role_name
		role.desk_access = 1
		role.insert(ignore_permissions=True)


def ensure_default_settings():
	"""Store default settings that were never saved. Values an admin already set are kept."""
	singles = frappe.qb.Table("tabSingles")
	stored_fields = set(
		frappe.qb.from_(singles)
		.select(singles.field)
		.where(singles.doctype == SETTINGS_DOCTYPE)
		.run(pluck=True)
	)
	missing = {key: value for key, value in DEFAULT_SETTINGS.items() if key not in stored_fields}
	if not missing:
		return
	settings = frappe.get_single(SETTINGS_DOCTYPE)
	settings.update(missing)
	settings.save(ignore_permissions=True)


def remove_roles():
	"""Remove the app's roles and their assignments. Never blocks uninstall."""
	try:
		frappe.db.delete("Has Role", {"role": ("in", ROLES)})
		frappe.db.delete("Custom DocPerm", {"role": ("in", ROLES)})
		for role_name in ROLES:
			frappe.delete_doc("Role", role_name, ignore_missing=True, force=True, ignore_permissions=True)
	except Exception:
		frappe.log_error(title="Assessment Hub: role cleanup failed during uninstall")
		click.secho("Assessment Hub: could not remove roles, see Error Log.", fg="yellow")


def remove_app_level_records():
	"""Desktop Icon / Workspace Sidebar are app-level in v16 and may not be removed via Module Def."""
	try:
		for doctype in ("Desktop Icon", "Workspace Sidebar"):
			if frappe.db.table_exists(doctype):
				for name in frappe.get_all(doctype, filters={"app": "assessment_hub"}, pluck="name"):
					frappe.delete_doc(doctype, name, ignore_missing=True, force=True, ignore_permissions=True)
	except Exception:
		frappe.log_error(title="Assessment Hub: app-level record cleanup failed during uninstall")
