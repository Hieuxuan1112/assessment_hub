# Partner API Contract — Assessment Hub v1

## 1. Base URL and authentication

```
/api/v2/method/assessment_hub.api.v1.<module>.<function>
```

`/api/method/assessment_hub.api.v1.<module>.<function>` (the v1 route) also works, but its success envelope is `{"message": ...}` instead of `{"data": ...}`. All examples in this document use the v2 route.

Authentication uses Frappe's standard token scheme:

```
Authorization: token <api_key>:<api_secret>
```

To generate keys for a partner account: open the **User** form for that account in Desk → **Settings** section → **API Access** → **Generate Keys**. The account must have the **Assessment Manager** or **Assessment Viewer** role, matching the endpoint it needs to call.

## 2. Response envelope

**Success** — HTTP 200, the endpoint's return value under `data`:

```json
{"data": { }}
```

**Failure** — a matching HTTP status, and:

```json
{"errors": [{"message": "Human-readable message", "code": "ERROR_CODE"}]}
```

| Code | HTTP | When |
|---|---|---|
| `MISSING_PARAMETER` | 400 | a required parameter is absent or blank |
| `INVALID_PARAMETER` | 400 | a parameter has the wrong type, is out of range, or an invalid choice |
| `PERMISSION_DENIED` | 403 | the account's role does not allow the action |
| `NOT_FOUND` | 404 | the referenced Assessment does not exist |
| `INVALID_STATE` | 409 | the Assessment is Archived and cannot accept new/changed Questions |
| `VALIDATION_ERROR` | 422 | any other business-rule failure (e.g. duplicate/negative answer, too few answers) |
| `INTERNAL_ERROR` | 500 | an unexpected server error; logged to Error Log, response includes a reference id |

**Authentication failures and wrong HTTP methods never reach the app's error envelope** — Frappe rejects them before `assessment_hub` code runs, and returns its own body. Both cases below were captured against this app and return **HTTP 403** with `type: "PermissionError"`:

- No/invalid token — `{"errors":[{"type":"PermissionError","message":"You are not permitted to access this resource. Login to access...","title":"Method Not Allowed", ...}]}`
- Wrong HTTP method (e.g. `GET` on a `POST`-only endpoint) — `{"errors":[{"type":"PermissionError","message":"Not permitted", ...}]}`

On a site with `developer_mode` enabled (the dev site used to capture these examples), Frappe's own error body also includes a full `exception` traceback string; on a production site (`developer_mode` off) that field is omitted.

## 3. Pagination

Every list endpoint accepts:

| Parameter | Type | Rule |
|---|---|---|
| `page_length` | int | 1..`Assessment Hub Settings.max_page_length`; default `Assessment Hub Settings.default_page_length` |
| `start` | int | offset, ≥ 0. Mutually exclusive with `page` |
| `page` | int | 1-based page number, ≥ 1. Mutually exclusive with `start` |

Response includes:

```json
"pagination": {"start": 0, "page_length": 20, "has_more": true, "next_start": 20}
```

`next_start` is `null` when `has_more` is `false`.

**Incremental sync recipe:** call `list_assessments` with `updated_since=<last synced max updated_at>`; the results are sorted **ascending** by `updated_at` in that mode (instead of the default newest-first). Follow `pagination.next_start` until `has_more` is `false`, remember the last item's `updated_at` as the new watermark for next time, and de-duplicate by `id` (the filter is `>=`, so the watermark row itself may repeat once).

## 4. Objects

**Assessment**

| Field | Type | Notes |
|---|---|---|
| `id` | string | `ASM-#####` |
| `title` | string | |
| `description` | string \| null | |
| `status` | string | `Draft` \| `Published` \| `Archived` |
| `created_at` | string | ISO-8601, site timezone |
| `updated_at` | string | ISO-8601, site timezone |

**Question** (adds `answers` only when the caller asked for them)

| Field | Type | Notes |
|---|---|---|
| `id` | string | `QST-######` |
| `assessment_id` | string | |
| `content` | string | HTML from a Text Editor field, sanitized on save |
| `sort_order` | int | ascending order within its assessment |
| `status` | string | `Active` \| `Inactive` |
| `created_at` | string | ISO-8601 |
| `updated_at` | string | ISO-8601 |
| `answers` | array\<Answer\> | only present when requested |

**Answer**

| Field | Type | Notes |
|---|---|---|
| `id` | string | child-row name |
| `content` | string | |
| `score` | float | |
| `sort_order` | int | |

## 5. Endpoints

### `GET assessments.list_assessments`

| Parameter | Required | Rule |
|---|---|---|
| `status` | no | `Draft` \| `Published` \| `Archived` |
| `search` | no | substring match on `title` (case-insensitive `LIKE`; `%`/`_` in your search text are treated literally, not as wildcards) |
| `updated_since` | no | datetime, e.g. `2026-09-17 08:30:00`; filters `updated_at >= value` and switches sort to ascending |
| `page_length`, `start` / `page` | no | see §3 |

```bash
curl -s "http://assessment.localhost:8010/api/v2/method/assessment_hub.api.v1.assessments.list_assessments?page_length=2" \
  -H "Authorization: token $VIEWER_TOKEN"
```

Success (200):

```json
{
    "data": {
        "items": [
            {
                "id": "ASM-00008",
                "title": "XSS probe <img src=\"x\">",
                "description": "Sample assessment (Draft)",
                "status": "Draft",
                "created_at": "2026-09-18T13:18:20.016751",
                "updated_at": "2026-09-18T13:18:20.016751"
            },
            {
                "id": "ASM-00006",
                "title": "Legacy SQL Quiz",
                "description": "Sample assessment (Archived)",
                "status": "Archived",
                "created_at": "2026-09-18T13:18:19.979506",
                "updated_at": "2026-09-18T13:18:20.010455"
            }
        ],
        "pagination": {"start": 0, "page_length": 2, "has_more": true, "next_start": 2}
    }
}
```

### `GET assessments.get_assessment`

| Parameter | Required | Rule |
|---|---|---|
| `id` | yes | Assessment name |
| `include_questions` | no | `1`/`0`/`true`/`false`; when true, nests every Question (with its `answers`) ordered by `sort_order` |

```bash
curl -s "http://assessment.localhost:8010/api/v2/method/assessment_hub.api.v1.assessments.get_assessment?id=ASM-00001&include_questions=1" \
  -H "Authorization: token $VIEWER_TOKEN"
```

Success (200), trimmed to one question:

```json
{
    "data": {
        "id": "ASM-00001",
        "title": "Python Fundamentals",
        "description": "Sample assessment (Published)",
        "status": "Published",
        "created_at": "2026-09-18T13:18:19.317335",
        "updated_at": "2026-09-18T13:18:19.894691",
        "questions": [
            {
                "id": "QST-000002",
                "assessment_id": "ASM-00001",
                "content": "<p>Which keyword defines a function in Python?</p>",
                "sort_order": 1,
                "status": "Active",
                "created_at": "2026-09-18T13:18:19.831559",
                "updated_at": "2026-09-18T13:18:19.831559",
                "answers": [
                    {"id": "ft69ob3ouf", "content": "def", "score": 1.0, "sort_order": 1},
                    {"id": "ft6mdn7f57", "content": "func", "score": 0.0, "sort_order": 2}
                ]
            }
        ]
    }
}
```

Error, unknown id (404):

```bash
curl -s "http://assessment.localhost:8010/api/v2/method/assessment_hub.api.v1.assessments.get_assessment?id=ASM-99999999" \
  -H "Authorization: token $VIEWER_TOKEN"
```

```json
{"errors": [{"message": "Assessment ASM-99999999 not found", "code": "NOT_FOUND"}]}
```

### `GET questions.list_questions`

| Parameter | Required | Rule |
|---|---|---|
| `assessment_id` | yes | 404 if the assessment does not exist |
| `status` | no | `Active` \| `Inactive` |
| `include_answers` | no | `1`/`0`/`true`/`false` |
| `page_length`, `start` / `page` | no | see §3 |

Items are always ordered `sort_order` ascending.

```bash
curl -s "http://assessment.localhost:8010/api/v2/method/assessment_hub.api.v1.questions.list_questions?assessment_id=ASM-00001&include_answers=1" \
  -H "Authorization: token $VIEWER_TOKEN"
```

Error, missing required parameter (400):

```bash
curl -s "http://assessment.localhost:8010/api/v2/method/assessment_hub.api.v1.questions.list_questions" \
  -H "Authorization: token $VIEWER_TOKEN"
```

```json
{"errors": [{"message": "Parameter 'assessment_id' is required.", "code": "MISSING_PARAMETER"}]}
```

### `POST questions.create_question`

Requires the **Assessment Manager** role. Creates the Question and all its Answers in one atomic write: if any answer fails validation, or anything fails after the rows are written, everything is rolled back together (see `docs/ARCHITECTURE.md` §2 and §7).

| Field | Required | Rule |
|---|---|---|
| `assessment_id` | yes | must exist and must not be `Archived` (409 `INVALID_STATE`) |
| `content` | yes | question HTML, max 10000 chars |
| `sort_order` | no | ≥ 1; auto-assigned (last + 1) if omitted |
| `status` | no | `Active` (default) \| `Inactive` |
| `answers` | yes | JSON array (or a JSON-encoded string), 1–50 items, each `{"content": str, "score": number, "sort_order"?: int}` |

```bash
curl -s -X POST "http://assessment.localhost:8010/api/v2/method/assessment_hub.api.v1.questions.create_question" \
  -H "Authorization: token $MANAGER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "assessment_id": "ASM-00004",
        "content": "<p>Which file registers doc_events?</p>",
        "answers": [
          {"content": "hooks.py", "score": 1},
          {"content": "setup.py", "score": 0}
        ]
      }'
```

Success (200):

```json
{
    "data": {
        "id": "QST-000011",
        "assessment_id": "ASM-00004",
        "content": "<p>Which file registers doc_events?</p>",
        "sort_order": 3,
        "status": "Active",
        "created_at": "2026-09-18T07:33:41.606462",
        "updated_at": "2026-09-18T07:33:41.606462",
        "answers": [
            {"id": "gpoup2rnvd", "content": "hooks.py", "score": 1.0, "sort_order": 1},
            {"id": "gpomlebqfb", "content": "setup.py", "score": 0.0, "sort_order": 2}
        ]
    }
}
```

Error, Viewer role (403):

```json
{"errors": [{"message": "You do not have permission to perform this action.", "code": "PERMISSION_DENIED"}]}
```

Error, Archived assessment (409):

```json
{"errors": [{"message": "Assessment ASM-00006 is archived; its questions cannot be added or changed.", "code": "INVALID_STATE"}]}
```

## 6. Postman collection

`docs/postman/assessment_hub.postman_collection.json` — import it, set the collection variables `base_url`, `manager_token`, `viewer_token` and `assessment_id`, and run the requests top to bottom (list → get → create → list questions → error examples).
