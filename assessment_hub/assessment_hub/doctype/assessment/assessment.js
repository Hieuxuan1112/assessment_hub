// Copyright (c) 2026, Ngo Xuan Hieu and contributors
// For license information, please see license.txt

frappe.ui.form.on("Assessment", {
	refresh(frm) {
		const $preview = frm.fields_dict.questions_html.$wrapper;
		if (frm.is_new()) {
			$preview.empty();
			return;
		}

		add_status_actions(frm);
		render_questions_preview(frm);

		if (frm.doc.status === "Archived") {
			frm.set_intro(__("This assessment is archived and read-only."), "orange");
			frm.disable_form();
		}
	},
});

function add_status_actions(frm) {
	const can_write = frappe.model.can_write("Assessment");
	const actions = __("Actions");

	if (can_write && frm.doc.status === "Draft") {
		frm.add_custom_button(__("Publish"), () => run_transition(frm, "publish"), actions);
	}

	if (can_write && frm.doc.status !== "Archived") {
		frm.add_custom_button(
			__("Archive"),
			() =>
				frappe.confirm(
					__(
						"Archive this assessment? It becomes read-only and cannot receive new questions."
					),
					() => run_transition(frm, "archive")
				),
			actions
		);
	}

	if (frm.doc.status !== "Archived" && frappe.model.can_create("Assessment Question")) {
		frm.add_custom_button(__("Add Question"), () =>
			frappe.new_doc("Assessment Question", { assessment: frm.doc.name })
		);
	}
}

function run_transition(frm, method) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Please save your changes first."));
		return;
	}
	frm.call({ method, doc: frm.doc, freeze: true }).then(() => frm.reload_doc());
}

function render_questions_preview(frm) {
	const $wrapper = frm.fields_dict.questions_html.$wrapper;
	const esc = frappe.utils.escape_html;
	$wrapper.html(`<p class="text-muted small">${esc(__("Loading questions..."))}</p>`);

	frappe.db
		.get_list("Assessment Question", {
			filters: { assessment: frm.doc.name },
			fields: ["name", "content", "status", "sort_order"],
			order_by: "sort_order asc",
			limit: 50,
		})
		.then((rows) => {
			if (!rows.length) {
				$wrapper.html(`<p class="text-muted small">${esc(__("No questions yet."))}</p>`);
				return;
			}

			// Every value is escaped: question content is user input and must never be injected as HTML.
			const body = rows
				.map((row) => {
					const plain_text = frappe.utils
						.unescape_html(strip_html(row.content || ""))
						.slice(0, 200);
					const color = row.status === "Active" ? "green" : "gray";
					const url = frappe.utils.get_form_link("Assessment Question", row.name);
					return `<tr>
						<td class="text-muted">${cint(row.sort_order)}</td>
						<td><a href="${esc(url)}">${esc(row.name)}</a></td>
						<td>${esc(plain_text)}</td>
						<td><span class="indicator-pill ${color}">${esc(__(row.status))}</span></td>
					</tr>`;
				})
				.join("");

			$wrapper.html(`<table class="table table-sm table-hover">
				<thead><tr>
					<th>#</th><th>${esc(__("Question"))}</th><th>${esc(__("Content"))}</th><th>${esc(
				__("Status")
			)}</th>
				</tr></thead>
				<tbody>${body}</tbody>
			</table>`);
		});
}
