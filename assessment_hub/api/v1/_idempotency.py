"""Idempotency for `create_question`.

A partner may send an `idempotency_key`. The key is stored (as a per-user hash, with a
unique index) on the Assessment Question it created, together with a fingerprint of the
request. Retrying the same key + same payload returns the original question instead of
creating a duplicate; the same key with a different payload is a 409.
"""

import hashlib
import json

import frappe
from frappe import _

from assessment_hub.exceptions import IdempotencyConflictError

QUESTION_DOCTYPE = "Assessment Question"


def key_hash(user: str, key: str) -> str:
	return hashlib.sha256(f"{user}\0{key}".encode()).hexdigest()


def fingerprint(payload: dict) -> str:
	canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
	return hashlib.sha256(canonical.encode()).hexdigest()


def find_existing(hashed_key: str):
	return frappe.db.get_value(
		QUESTION_DOCTYPE, {"idempotency_key": hashed_key}, ["name", "request_fingerprint"], as_dict=True
	)


def ensure_same_request(existing, request_fingerprint: str) -> None:
	if existing.request_fingerprint != request_fingerprint:
		raise IdempotencyConflictError(
			_("This idempotency_key was already used with a different request body.")
		)
