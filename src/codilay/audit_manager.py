import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class AuditManager:
    """
    Manages running audits against the CodiLay documented codebase.

    Two modes:
    - passive: Audit planner — uses CODEBASE.md + wire graph to identify areas of concern
      and produce a prioritized file reading list. Fast but produces suspicions, not findings.
    - active: Real audit — triages relevant files from docs, reads actual source, produces
      findings tied to specific lines with evidence from real code.
    """

    AUDIT_TYPES = {
        "security": "Find vulnerabilities (XSS, auth flaws, secrets, etc.)",
        "code_quality": "Readability, structure, maintainability",
        "performance": "Speed, memory, CPU, DB efficiency. Provide a thorough, complete report without truncation.",
        "architecture": "System design, scalability, service boundaries",
        "business_logic": "Core logic correctness (payments, rules, flows)",
        "appsec": "Application Security: Code-level + runtime vulnerabilities",
        "infra_sec": "Infrastructure Security: Servers, cloud configs, firewalls",
        "network_sec": "Network Security: Ports, traffic, internal communication",
        "api_sec": "API Security: Rate limiting, auth, data exposure",
        "authz": "Authentication & Authorization: JWT, OAuth, role-based access",
        "crypto": "Cryptography: Encryption correctness, key storage",
        "secrets": "Secrets Management: API keys, env leaks",
        "dependencies": "Dependency / Supply Chain: npm/pip packages risks",
        "container_sec": "Container Security: Docker images, vulnerabilities",
        "cloud_sec": "Cloud Security: IAM roles, S3 leaks, misconfigurations",
        "mobile_sec": "Mobile Security: Reverse engineering, insecure storage",
        "frontend_sec": "Frontend Security: XSS, CSP, browser risks",
        "pentest": "Penetration Testing (Pentest): Simulated real-world attacks",
        "ci_cd": "CI/CD Pipeline: Secure deployments, no secret leaks",
        "vcs": "Version Control: Git practices, exposed history, bad commits",
        "code_review": "Code Review Process: Are PRs reviewed properly?",
        "workflow": "Dev Workflow: Branching, release cycles",
        "testing": "Testing: Unit/integration/e2e coverage",
        "qa": "QA Process: Manual + automated QA quality",
        "reliability": "Reliability: System uptime, failure handling",
        "chaos": "Chaos Engineering: How system behaves under failure",
        "database": "Database: Indexing, queries, normalization",
        "data_integrity": "Data Integrity: Correctness and consistency of data",
        "data_privacy": "Data Privacy: Personal data handling",
        "data_gov": "Data Governance: Ownership, lifecycle, policies",
        "load": "Load Testing: How system behaves under traffic",
        "stress": "Stress Testing: Breaking point analysis",
        "scalability": "Scalability: Can it grow to 10x users?",
        "caching": "Caching: Redis/memory usage efficiency",
        "ux_ui": "UX/UI Audit: Usability, accessibility, friction",
        "a11y": "Accessibility (a11y): Screen readers, keyboard nav",
        "seo": "SEO (for web apps): Indexing, performance, metadata",
        "compliance": "Compliance: Regulations like GDPR",
        "license": "License: Open-source license violations",
        "audit_logs": "Audit Logging Review: Are actions tracked properly?",
        "observability": "Observability: Logs, metrics, tracing",
        "monitoring": "Monitoring: Alerts, dashboards",
        "incident_response": "Incident Response: How team reacts to outages",
        "disaster_recovery": "Disaster Recovery: Backups, failover systems",
        "cost": "Cost (FinOps): Cloud cost optimization",
        "ai_ml": "AI/ML Audit: Model bias, data leakage",
        "algorithm": "Algorithm Audit: Efficiency, correctness",
        "reversing": "Reverse Engineering Audit: Can attackers decompile your app?",
    }

    # Cap per-file size sent to LLM (~12k tokens)
    MAX_FILE_CHARS = 50_000
    MAX_TRIAGE_FILES = 25

    def __init__(self, llm_client, output_dir: str):
        self.llm = llm_client
        self.output_dir = output_dir
        self.audits_dir = os.path.join(self.output_dir, "audits")
        os.makedirs(self.audits_dir, exist_ok=True)
        self.index_path = os.path.join(self.audits_dir, "audit_index.json")

    def get_index(self) -> Dict[str, Any]:
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"runs": []}

    def save_index(self, index_data: Dict[str, Any]):
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2)

    # ── Passive mode (audit planner) ─────────────────────────────────────────

    def _build_planner_prompt(
        self, audit_type: str, sections: Dict[str, str], open_wires: List[Dict], closed_wires: List[Dict]
    ) -> str:
        """Build a prompt that produces an audit plan from documentation, not real findings."""
        description = self.AUDIT_TYPES.get(audit_type, audit_type)
        prompt = (
            f"You are an audit planner for a {description} audit.\n\n"
            "Based on the project documentation (NOT actual source code), identify:\n"
            "1. Which files or components are highest risk for this audit type\n"
            "2. What patterns or areas warrant deeper investigation\n"
            "3. A prioritized reading list for a follow-up active audit\n\n"
            "IMPORTANT: This is an AUDIT PLAN based on documentation only — not verified findings. "
            "State suspicions and what to verify, not definitive conclusions. "
            "Mark each concern with CONCERN: (not FINDING:) to distinguish from real audit results.\n\n"
            "Use this structure for each concern:\n"
            "CONCERN: <short title>\n"
            "Risk: <HIGH|MEDIUM|LOW>\n"
            "File: <suspected file path>\n"
            "Wire: <wire path or section id>\n"
            "Suspicion: <what might be wrong and why, based on docs>\n"
            "Verify: <what to check in the actual source to confirm>\n\n"
        )

        doc_summary = []
        for file_path, content in list(sections.items())[:100]:
            doc_summary.append(f"--- {file_path} ---\n{content}\n")
        prompt += "PROJECT DOCUMENTATION:\n\n" + "\n".join(doc_summary) + "\n\n"

        wire_info = (
            "CLOSED WIRES:\n" + json.dumps(closed_wires, indent=2) + "\n\n"
            "OPEN WIRES:\n" + json.dumps(open_wires, indent=2)
        )
        prompt += "WIRING INFORMATION:\n" + wire_info
        return prompt

    def _run_passive_audit(
        self,
        audit_type: str,
        section_contents: Dict[str, str],
        open_wires: List[Dict],
        closed_wires: List[Dict],
    ) -> Dict[str, Any]:
        """Audit planner: uses CODEBASE.md to identify areas of concern and prioritized files."""
        prompt = self._build_planner_prompt(audit_type, section_contents, open_wires, closed_wires)
        response_data = self.llm.call(
            "You are an expert auditor. Based on documentation, identify risk areas and files to audit.",
            prompt,
            json_mode=False,
        )
        response = response_data.get("answer", "") if isinstance(response_data, dict) else str(response_data)
        return self._save_report(audit_type, "passive", response, [])

    # ── Active mode (real source audit) ──────────────────────────────────────

    def _triage_relevant_files(
        self,
        audit_type: str,
        section_contents: Dict[str, str],
        open_wires: List[Dict],
        closed_wires: List[Dict],
        all_files: List[str],
    ) -> List[Dict]:
        """Phase 1: Ask LLM to identify the most relevant files for this audit type."""
        description = self.AUDIT_TYPES.get(audit_type, audit_type)

        doc_summary = []
        for file_path, content in list(section_contents.items())[:60]:
            doc_summary.append(f"--- {file_path} ---\n{content[:600]}\n")

        wire_summary = json.dumps({"open": open_wires[:30], "closed": closed_wires[:30]}, indent=2)
        file_list = "\n".join(all_files)

        prompt = (
            f"You are selecting files for a {description} audit.\n\n"
            f"Available files:\n{file_list}\n\n"
            f"Project documentation summary:\n{''.join(doc_summary)}\n\n"
            f"Wire dependency information:\n{wire_summary}\n\n"
            f"Return a JSON array of up to {self.MAX_TRIAGE_FILES} files most relevant to this audit type.\n"
            'Each item: {"path": "relative/file/path", "relevance": 0.0-1.0, "reason": "why relevant"}\n'
            "Sort by relevance descending. Only include paths that appear exactly in the available files list.\n"
            "Return ONLY the JSON array, no other text."
        )

        response_data = self.llm.call(
            "You are an expert auditor selecting files for targeted code review. Return only JSON.",
            prompt,
            json_mode=False,
        )
        answer = response_data.get("answer", "") if isinstance(response_data, dict) else str(response_data)

        try:
            start = answer.find("[")
            end = answer.rfind("]") + 1
            if start >= 0 and end > start:
                candidates = json.loads(answer[start:end])
                all_files_set = set(all_files)
                return [c for c in candidates if isinstance(c, dict) and c.get("path") in all_files_set]
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: first 15 files
        return [{"path": f, "relevance": 0.5, "reason": "fallback selection"} for f in all_files[:15]]

    def _read_file_with_lines(self, scanner, file_path: str) -> Optional[str]:
        """Read a source file and prepend line numbers for precise LLM references."""
        full_path = os.path.join(scanner.target_path, file_path)
        content = scanner.read_file(full_path)
        if not content:
            return None
        if len(content) > self.MAX_FILE_CHARS:
            content = content[: self.MAX_FILE_CHARS] + "\n... [truncated at 50k chars]"
        lines = content.splitlines()
        return "\n".join(f"{i + 1:4d} | {line}" for i, line in enumerate(lines))

    def _build_active_audit_prompt(
        self,
        audit_type: str,
        file_sources: Dict[str, str],
        open_wires: List[Dict],
        closed_wires: List[Dict],
    ) -> str:
        """Build a prompt that audits actual source code."""
        description = self.AUDIT_TYPES.get(audit_type, audit_type)
        prompt = (
            f"Run a {description} audit on the actual source code below.\n\n"
            "Each finding MUST be a separate block starting with 'FINDING:' separated by double newlines.\n\n"
            "Use this exact structure for each finding:\n"
            "FINDING: <short title>\n"
            "Severity: <HIGH|MEDIUM|LOW>\n"
            "File: <file path>\n"
            "Line: <line number(s), e.g. 47 or 42-55>\n"
            "Evidence: <exact code snippet or quoted line that demonstrates the issue>\n"
            "Impact: <business or technical impact>\n"
            "Fix: <specific actionable recommendation>\n\n"
            "Rules:\n"
            "- Reference exact line numbers from the numbered source below\n"
            "- Quote the actual code in Evidence — do not paraphrase\n"
            "- For data-flow issues (injection, XSS), trace the wire path from entry point to sink\n"
            "- Do not invent findings — only report what is visible in the provided source\n\n"
        )

        wire_info = (
            "DEPENDENCY WIRES (use to trace data flows across files):\n"
            "CLOSED WIRES:\n" + json.dumps(closed_wires[:40], indent=2) + "\n\n"
            "OPEN WIRES:\n" + json.dumps(open_wires[:20], indent=2) + "\n\n"
        )
        prompt += wire_info

        prompt += "SOURCE FILES:\n\n"
        for file_path, content in file_sources.items():
            prompt += f"=== {file_path} ===\n{content}\n\n"

        return prompt

    def _run_active_audit(
        self,
        audit_type: str,
        section_contents: Dict[str, str],
        open_wires: List[Dict],
        closed_wires: List[Dict],
        target_path: str,
        scanner,
    ) -> Dict[str, Any]:
        """4-phase active audit: triage → read source → audit real code → report."""

        # Phase 1: identify relevant files using documentation as a map
        all_files = scanner.get_all_files()
        relevant = self._triage_relevant_files(audit_type, section_contents, open_wires, closed_wires, all_files)

        # Phase 2: read actual source files with line numbers
        file_sources: Dict[str, str] = {}
        for item in relevant:
            content = self._read_file_with_lines(scanner, item["path"])
            if content:
                file_sources[item["path"]] = content

        # Phase 3: audit real code
        prompt = self._build_active_audit_prompt(audit_type, file_sources, open_wires, closed_wires)
        response_data = self.llm.call(
            "You are an expert code auditor. Analyze actual source code and produce precise, line-referenced findings.",
            prompt,
            json_mode=False,
        )
        response = response_data.get("answer", "") if isinstance(response_data, dict) else str(response_data)

        # Phase 4: save report
        return self._save_report(audit_type, "active", response, relevant)

    # ── Shared ───────────────────────────────────────────────────────────────

    def _save_report(self, audit_type: str, mode: str, response: str, relevant_files: List[Dict]) -> Dict[str, Any]:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        report_filename = f"{audit_type}_{date_str}.md"
        report_path = os.path.join(self.audits_dir, report_filename)

        if mode == "active" and relevant_files:
            files_section = "\n".join(f"- {f['path']} (relevance: {f.get('relevance', '?')})" for f in relevant_files)
            header = (
                f"# {audit_type.upper()} Audit\n\n"
                f"Date: {date_str}\nMode: {mode}\n\n"
                f"## Files Audited\n\n{files_section}\n\n"
                f"## Findings\n\n"
            )
        else:
            header = (
                f"# {audit_type.upper()} Audit Plan\n\n"
                f"Date: {date_str}\nMode: {mode}\n\n"
                "> **Note**: This is an audit plan based on documentation only — not verified findings "
                "from actual source code. Run with `--mode active` for real line-referenced findings.\n\n"
            )

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(header + response + "\n")

        index = self.get_index()
        index["runs"].append(
            {
                "type": audit_type,
                "mode": mode,
                "date": datetime.now(timezone.utc).isoformat(),
                "report_file": report_filename,
                "files_audited": len(relevant_files),
            }
        )
        self.save_index(index)

        return {"report_path": report_path, "report_filename": report_filename, "response": response}

    def run_audit(
        self,
        audit_type: str,
        mode: str,
        section_contents: Dict[str, str],
        open_wires: List[Dict],
        closed_wires: List[Dict],
        target_path: str,
        scanner=None,
    ) -> Dict[str, Any]:
        """
        Run an audit.
        passive: Reads section_contents + wires, produces an audit plan (areas of concern).
        active:  Triages files via docs, reads actual source, produces line-referenced findings.
        """
        if mode == "active" and scanner is not None:
            return self._run_active_audit(audit_type, section_contents, open_wires, closed_wires, target_path, scanner)
        return self._run_passive_audit(audit_type, section_contents, open_wires, closed_wires)
