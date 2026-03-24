# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

**DO NOT** create public GitHub issues for security vulnerabilities.

### How to Report

1. **Email:** security@zinnia.com
2. **Subject:** `[SECURITY] Zinnia Axion - <Brief Description>`
3. **Include:**
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Response Timeline

- **Initial response:** Within 24 hours
- **Triage & assessment:** Within 48 hours
- **Fix & release:** Within 7 days (critical), 30 days (non-critical)

## Security Best Practices

### For Developers

1. **Never commit:**
   - `.env` files with real credentials
   - Database credentials
   - API keys or tokens
   - SSL certificates or private keys
   - Session files

2. **Always:**
   - Use `.env.example` with dummy values
   - Store secrets in AWS Secrets Manager
   - Review `.gitignore` before committing
   - Use environment variables for sensitive data
   - Run `git diff` before committing

3. **Code review:**
   - All changes require peer review
   - Security-sensitive changes require security team review
   - No direct commits to `main` branch

### For DevOps

1. **Secrets Management:**
   - Use AWS Secrets Manager for all credentials
   - Rotate secrets every 90 days
   - Never log secret values
   - Use IAM roles instead of long-lived credentials

2. **Network Security:**
   - Deploy backend in private subnets
   - Use security groups with least privilege
   - Enable VPC flow logs
   - Use ALB with SSL/TLS only

3. **Database Security:**
   - Enable encryption at rest
   - Enable encryption in transit
   - Use strong passwords (min 16 characters)
   - Restrict access to private subnets only
   - Enable automated backups

4. **Monitoring:**
   - Enable CloudWatch Logs
   - Set up CloudWatch Alarms
   - Enable AWS GuardDuty
   - Enable CloudTrail for audit logging

## Security Features

### Authentication & Authorization

- **Admin:** OIDC SSO (Microsoft Azure AD)
- **Tracker:** Device token authentication
- **RBAC:** Role-based access control
- **Team Isolation:** Hierarchical team visibility

### Data Protection

- **Encryption at Rest:** PostgreSQL encryption
- **Encryption in Transit:** HTTPS/TLS 1.2+
- **Data Minimization:** Only essential telemetry collected
- **Audit Logging:** All admin actions logged

### Application Security

- **CSRF Protection:** Flask-WTF
- **Rate Limiting:** Flask-Limiter
- **SQL Injection:** SQLAlchemy ORM (parameterized queries)
- **XSS Protection:** Content-Security-Policy headers
- **Session Security:** HTTP-only, secure cookies

### Infrastructure Security

- **Container Scanning:** Scan Docker images for vulnerabilities
- **Dependency Scanning:** Automated security updates
- **Secret Scanning:** GitHub secret scanning enabled
- **Network Isolation:** Private subnets, security groups

## Compliance

- **Data Privacy:** Employee consent required
- **Data Retention:** 90 days hot, archival for compliance
- **Access Logs:** 1-year retention
- **Incident Response:** 24-hour response SLA

## Security Contacts

- **Security Team:** security@zinnia.com
- **Privacy Team:** privacy@zinnia.com
- **Compliance:** compliance@zinnia.com

## Acknowledgments

We appreciate security researchers who responsibly disclose vulnerabilities. Qualified reports may be eligible for recognition in our Hall of Fame.

---

**Last Updated:** March 2026  
**Next Review:** June 2026
