import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List


class AuditManager:
    """
    Manages running audits against the CodiLay documented codebase.
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

    def _build_prompt(
        self, audit_type: str, mode: str, sections: Dict[str, str], open_wires: List[Dict], closed_wires: List[Dict]
    ) -> str:
        prompt = f"Run a {mode.upper()} audit for category: {self.AUDIT_TYPES.get(audit_type, audit_type)}.\n\n"
        prompt += (
            f"Please output your findings clearly. Each finding MUST be a separate block "
            f"starting with 'FINDING:' and separated by double newlines.\n"
        )
        prompt += "Strictly use this field structure for each finding:\n"
        prompt += (
            "FINDING: <short title>\nSeverity: <HIGH|MEDIUM|LOW>\nFile: <file path>\n"
            "Wire: <wire path or section id>\nEvidence: <detailed explanation of the finding>\n"
            "Impact: <business or technical impact>\nFix: <specific recommendation to resolve>\n\n"
        )

        # Combine docs to some limit to avoid massive context
        doc_summary = []
        for file_path, content in list(sections.items())[:100]:  # Limit for token safety
            doc_summary.append(f"--- {file_path} ---\n{content}\n")

        doc_text = "\n".join(doc_summary)

        wire_info = (
            "CLOSED WIRES:\n" + json.dumps(closed_wires, indent=2) + "\n\n"
            "OPEN WIRES:\n" + json.dumps(open_wires, indent=2)
        )

        prompt += (
            f"Here is the project documentation context:\n\n{doc_text}\n\n"
            f"Here is the wiring information:\n{wire_info}\n"
        )
        prompt += "\nGo systematically through the architecture and provide actionable findings."
        prompt += "\n\nCRITICAL FOR READABILITY:"
        prompt += "\n- Use clear, short executive-style titles for FINDING."
        prompt += "\n- Keep Evidence sections dense but punchy."
        prompt += "\n- Use bullet points for Evidence and Fix when listing multiple items."
        prompt += "\n- Focus on the 'Why' (Impact) to grab attention immediately."
        return prompt

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
        Run a passive or active audit.
        Passive: Reads section_contents + wires, generates findings.
        Active: Plucks relevant files + content, generates findings.
        """
        prompt = self._build_prompt(audit_type, mode, section_contents, open_wires, closed_wires)

        response_data = self.llm.call(
            "You are an expert security and architecture auditor. Provide specific file and line numbers.",
            prompt,
            json_mode=False,
        )
        response = response_data.get("answer", "") if isinstance(response_data, dict) else str(response_data)

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        report_filename = f"{audit_type}_{date_str}.md"
        report_path = os.path.join(self.audits_dir, report_filename)

        report_content = f"# {audit_type.upper()} Audit\n\nDate: {date_str}\nMode: {mode}\n\n{response}\n"

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        # Update index
        index = self.get_index()
        index["runs"].append(
            {
                "type": audit_type,
                "mode": mode,
                "date": datetime.now(timezone.utc).isoformat(),
                "report_file": report_filename,
            }
        )
        self.save_index(index)

        return {"report_path": report_path, "report_filename": report_filename, "response": response}
