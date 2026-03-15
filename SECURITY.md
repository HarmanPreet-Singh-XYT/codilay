# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take the security of CodyLay seriously. If you believe you have found a security vulnerability, please report it to us by following these steps:

1.  **Do not** open a public issue.
2.  Send an email to security@codylay.ai (placeholder) or contact the maintainers directly through official channels.
3.  Include a detailed description of the vulnerability, including steps to reproduce and potential impact.

We will acknowledge your report within 48 hours and provide a timeline for a resolution. We request that you follow responsible disclosure practices and allow us to fix the issue before sharing any details publicly.

### Potential Security Areas

- **API Keys**: CodyLay handles sensitive API keys for LLM providers. These should always be stored in environment variables and never committed to version control.
- **Code Submission**: CodyLay sends your source code to LLM providers (Anthropic, OpenAI, etc.). Ensure you are aware of the privacy policies of the providers you use.
- **Local State**: The `.codylay_state.json` file contains information about your project structure. Keep this file secure if your project is private.
