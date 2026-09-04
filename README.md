# Shadow C2 — Web Backdoor Generator & C2 Command Center

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   OPERATOR DASHBOARD                     │
│  ┌─────────┬──────────┬──────────┬─────────┬─────────┐  │
│  │Dashboard│ Victims  │Generator │  Recon  │Terminal │  │
│  └────┬────┴────┬─────┴────┬─────┴────┬────┴────┬────┘  │
│       └─────────┴──────────┴──────────┴─────────┘        │
│                    Flask + SocketIO                        │
├─────────────────────────────────────────────────────────┤
│                    C2 HANDLER                              │
│  ┌──────────┬──────────┬──────────┬──────────┐           │
│  │  HTTPS   │   DNS    │  WebSocket│  ICMP   │           │
│  │ :8443    │  :5353   │  (same)   │ (raw)   │           │
│  └──────────┴──────────┴──────────┴──────────┘           │
├─────────────────────────────────────────────────────────┤
│  GENERATOR ENGINE                                         │
│  Template → Sandbox → AV → WAF → Poly → Meta → Obf → Enc│
└─────────────────────────────────────────────────────────┘
```

## Quick Start (Ubuntu)

```bash
git clone <repo> && cd shadow-c2
chmod +x setup.sh && sudo ./setup.sh
source venv/bin/activate
source .env
python -m server.app
```

Dashboard: `https://localhost:8443/dashboard/`
Default: `operator` / `shadowc2`

## Features

### Multi-Channel C2
- **HTTPS** (port 8443) — Primary channel, stealth headers, beacon jitter
- **WebSocket** — Real-time bidirectional via Socket.IO
- **DNS Tunneling** (port 5353) — Data in subdomain labels, TXT record responses
- **ICMP** — Echo request/reply with magic marker (needs root)
- **Social Media** — Discord/Telegram bot API (optional)

### Payload Generator
- **Templates**: PHP, ASP.NET/ASPX, JSP, Python, .htaccess, .user.ini
- **Polymorphic Engine**: Variable/function randomization, dead code, control flow flattening, opaque predicates
- **Metamorphic Engine**: Function substitution, loop transforms, conditional inversion
- **Obfuscator**: String encryption (XOR), function call encoding (6 methods), variable mangling
- **Encoding Chain**: base64, rot13, XOR, AES-256-CBC, gzip, hex, octal, reverse, chr_array, custom substitution
- **Polyglot Files**: GIF89a+PHP, JPEG+PHP, PNG+PHP, PDF+PHP, SVG+PHP (valid image headers, pass getimagesize())
- **WAF Bypass**: Cloudflare, ModSecurity, Sucuri, Imperva, AWS WAF, Akamai
- **AV/EDR Bypass**: Sandbox detection, timing checks, environment validation, scanner detection
- **Every generation produces a unique hash** — no two payloads are identical

### Backdoor Features
- Multi-method command execution (system/exec/shell_exec/passthru/popen/proc_open + backtick fallback)
- File operations (ls/read/write/delete/upload)
- Credential finder (WordPress, Laravel/.env, Joomla configs)
- Persistence installer (cron, .htaccess, .user.ini, SSH key injection)
- Self-destruct capability
- AES-256-CBC + XOR encryption for C2 comms
- CMS auto-detection on registration

### Recon Module
- Target fingerprinting (server, OS, technologies, security headers)
- WAF detection (10 WAF signature databases)
- CMS detection (WordPress, Joomla, Drupal, Magento, Shopify with version)
- Port scanner (TCP connect, service detection, banner grabbing)

### Operator Dashboard
- Dark theme web UI
- Global victim map (Leaflet.js with CartoDB dark tiles)
- Real-time stats and activity feed
- Interactive terminal per victim
- File manager with upload/download
- Credential database with CSV export
- Broadcast commands to all victims

## Configuration

All settings via environment variables (`SC2_` prefix):

| Variable | Default | Description |
|----------|---------|-------------|
| `SC2_HOST` | `0.0.0.0` | Bind address |
| `SC2_PORT` | `8443` | HTTPS port |
| `SC2_USERNAME` | `operator` | Dashboard login |
| `SC2_PASSWORD` | `shadowc2` | Dashboard password |
| `SC2_DNS_ENABLED` | `true` | Enable DNS channel |
| `SC2_DNS_PORT` | `5353` | DNS listener port |
| `SC2_DNS_DOMAIN` | `c2.local` | DNS tunnel domain |
| `SC2_ICMP_ENABLED` | `false` | Enable ICMP (needs root) |
| `SC2_DISCORD_TOKEN` | (empty) | Discord bot token |
| `SC2_TELEGRAM_TOKEN` | (empty) | Telegram bot token |

## Wire Protocol

Custom binary: `MAGIC(4) + VERSION(1) + MSG_TYPE(1) + SEQ(4) + LEN(4) + CRC32(4)` = 18-byte header

Encryption: X25519 ECDH → HKDF → AES-256-GCM per session

## File Structure

```
├── server/
│   ├── app.py                  # Main entry point
│   ├── config.py               # Central configuration
│   ├── database.py             # SQLite layer (8 tables)
│   ├── c2/
│   │   ├── crypto.py           # Session keys, ECDH, key rotation
│   │   ├── protocol.py         # Wire protocol, fragmentation
│   │   ├── handler.py          # Central C2 handler
│   │   └── channels/
│   │       ├── https_channel.py
│   │       ├── dns_channel.py
│   │       ├── ws_channel.py
│   │       ├── icmp_channel.py
│   │       └── social_channel.py
│   ├── generator/
│   │   ├── engine.py           # Orchestrator
│   │   ├── polymorphic.py      # Name randomization, dead code, CFG
│   │   ├── metamorphic.py      # Function substitution, transforms
│   │   ├── obfuscator.py       # String encryption, call encoding
│   │   ├── encoder.py          # 10-layer encoding chain
│   │   ├── waf_bypass.py       # WAF-specific evasion
│   │   ├── av_bypass.py        # AV/EDR bypass
│   │   ├── sandbox_detect.py   # VM/sandbox/debugger detection
│   │   ├── polyglot.py         # Image+PHP polyglot files
│   │   └── templates/          # PHP, ASP, JSP, Python templates
│   ├── recon/
│   │   ├── fingerprint.py      # Target fingerprinting
│   │   ├── waf_detect.py       # WAF detection
│   │   ├── cms_detect.py       # CMS detection
│   │   └── port_scan.py        # Port scanner
│   ├── routes/
│   │   ├── api.py              # C2 API endpoints
│   │   └── dashboard.py        # Operator web routes
│   └── utils/
│       ├── crypto_utils.py     # AES, X25519, HKDF, certs
│       ├── network.py          # HTTP, DNS, raw sockets
│       └── geo.py              # GeoIP lookup
├── frontend/
│   ├── templates/              # Jinja2 HTML templates
│   └── static/
│       └── css/dashboard.css   # Dark theme
├── requirements.txt
├── setup.sh
└── README.md
```
