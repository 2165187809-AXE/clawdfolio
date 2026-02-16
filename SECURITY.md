# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.x     | Yes       |
| < 2.0   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT open a public issue**
2. Use [GitHub Security Advisories](https://github.com/YichengYang-Ethan/clawdfolio/security/advisories/new) to report privately
3. Or email the maintainer directly

You should receive a response within 72 hours. We will work with you to understand the issue and coordinate a fix before public disclosure.

## Scope

Security concerns include but are not limited to:

- Credential or API key exposure
- Injection vulnerabilities in config parsing
- Unsafe deserialization
- Dependencies with known CVEs

## Best Practices for Users

- Never commit `config.yaml`, `.env`, or broker credentials to version control
- Use environment variables (`LONGPORT_APP_KEY`, etc.) for sensitive configuration
- Keep dependencies up to date (`pip install --upgrade clawdfolio`)
