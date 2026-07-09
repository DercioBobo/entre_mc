# Copyright (c) 2026, Dércio Bobo and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MCSettings(Document):
	pass


def get_settings():
	"""Cached accessor other doctypes/controllers use to read entre_mc config."""
	return frappe.get_cached_doc("MC Settings")
