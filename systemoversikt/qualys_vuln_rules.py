# -*- coding: utf-8 -*-
# Change log:
# 2026-06-21: Shared Qualys title-rule matching – decouple basisdrift and risk acceptance.


def title_matches(rule_title, vuln_title):
	return rule_title.lower() in vuln_title.lower()


def qualys_vuln_flags(vuln_title, *, basis_rules, acceptance_rules):
	ansvar_basisdrift = any(title_matches(r.title, vuln_title) for r in basis_rules)
	akseptert = any(title_matches(r.title, vuln_title) for r in acceptance_rules)
	return ansvar_basisdrift, akseptert
