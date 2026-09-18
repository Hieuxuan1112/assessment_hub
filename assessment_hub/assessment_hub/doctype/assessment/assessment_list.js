// Copyright (c) 2026, Ngo Xuan Hieu and contributors
// For license information, please see license.txt

const ASSESSMENT_STATUS_COLORS = {
	Draft: "gray",
	Published: "green",
	Archived: "red",
};

frappe.listview_settings["Assessment"] = {
	add_fields: ["status"],
	get_indicator(doc) {
		const color = ASSESSMENT_STATUS_COLORS[doc.status] || "gray";
		return [__(doc.status), color, `status,=,${doc.status}`];
	},
};
