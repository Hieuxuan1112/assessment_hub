// Copyright (c) 2026, Ngo Xuan Hieu and contributors
// For license information, please see license.txt

frappe.listview_settings["Assessment Question"] = {
	add_fields: ["status"],
	get_indicator(doc) {
		const color = doc.status === "Active" ? "green" : "gray";
		return [__(doc.status), color, `status,=,${doc.status}`];
	},
};
