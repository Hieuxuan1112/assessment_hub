// Copyright (c) 2026, Ngo Xuan Hieu and contributors
// For license information, please see license.txt

frappe.ui.form.on("Assessment Question", {
	setup(frm) {
		// Client-side guard: archived assessments are not offered in the link dropdown.
		frm.set_query("assessment", () => ({ filters: { status: ["!=", "Archived"] } }));
	},

	async refresh(frm) {
		if (frm.is_new() || !frm.doc.assessment) return;
		if ((await get_assessment_status(frm.doc.assessment)) === "Archived") {
			frm.set_intro(
				__("The linked assessment is archived, so this question is read-only."),
				"orange"
			);
			frm.disable_form();
		}
	},

	async assessment(frm) {
		if (!frm.doc.assessment) return;
		if ((await get_assessment_status(frm.doc.assessment)) === "Archived") {
			frappe.msgprint({
				title: __("Not allowed"),
				indicator: "red",
				message: __(
					"Assessment {0} is archived. Choose a Draft or Published assessment.",
					[frappe.utils.escape_html(frm.doc.assessment)]
				),
			});
			frm.set_value("assessment", "");
		}
	},
});

async function get_assessment_status(name) {
	const { message } = await frappe.db.get_value("Assessment", name, "status");
	return message && message.status;
}
