import json
import ssl
from http.server import BaseHTTPRequestHandler, HTTPServer

def image_uses_latest(image: str) -> bool:
    if not image: return True
    if "@" in image: return False
    last_part = image.rsplit("/", 1)[-1]
    if ":" not in last_part: return True
    tag = last_part.rsplit(":", 1)[1]
    return tag == "" or tag == "latest"

def container_has_cpu_limit(container: dict) -> bool:
    cpu = container.get("resources", {}).get("limits", {}).get("cpu")
    return cpu is not None and str(cpu).strip() != ""

def validate_pod(pod: dict) -> list:
    violations = []
    spec = pod.get("spec", {})
    containers = spec.get("containers", []) + spec.get("initContainers", [])
    for c in containers:
        name = c.get("name", "<unnamed>")
        image = c.get("image", "")
        if image_uses_latest(image):
            violations.append(f"Container '{name}' uses forbidden latest/missing tag")
        if not container_has_cpu_limit(c):
            violations.append(f"Container '{name}' is missing resources.limits.cpu")
    return violations

class WebhookServer(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/healthz"):
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok"); return
        self.send_response(404); self.end_headers()

    def do_POST(self):
        # FIX: Pura match karne ki jagah .startswith() use kiya takay ?timeout=3s bypass ho jaye
        if not self.path.startswith("/validate-pods"):
            self.send_response(404); self.end_headers(); return
        
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        
        request = body.get("request", {})
        uid = request.get("uid", "")
        pod = request.get("object", {})
        
        violations = validate_pod(pod)
        
        response_body = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "uid": uid,
                "allowed": len(violations) == 0
            }
        }
        
        if violations:
            response_body["response"]["status"] = {
                "code": 403,
                "message": "💥 Compliance Lockdown: " + " | ".join(violations)
            }
            
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response_body).encode("utf-8"))

if __name__ == "__main__":
    httpd = HTTPServer(("0.0.0.0", 8443), WebhookServer)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile="/tls/tls.crt", keyfile="/tls/tls.key")
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    print("Webhook listening on 8443...")
    httpd.serve_forever()