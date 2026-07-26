# Security policy

## Supported releases

Only the latest TERM Bridge release is supported. Deployments should enable
Home Assistant backups and apply security releases promptly.

## Reporting a vulnerability

Do not disclose suspected vulnerabilities in a public issue. Use GitHub private
vulnerability reporting for this repository. Include affected versions,
reproduction steps, impact, and any suggested mitigation.

## Deployment baseline

- Keep Home Assistant OS, Supervisor, and TERM Bridge current.
- Use MQTT TLS with hostname verification.
- Use a dedicated MQTT account restricted to the `term_bridge/#` and required
  Home Assistant discovery topics.
- Store certificates in the add-on-specific `/config` directory.
- Leave Home Assistant protection mode and its default AppArmor profile enabled.
- Do not expose MQTT or the add-on directly to the public internet.
- Review automated dependency, base-image, and workflow-action updates.

The project minimizes privileges and automates recurring security checks, but no
networked software can be safely guaranteed maintenance-free for ten years.
At minimum, review security alerts and available updates quarterly.
