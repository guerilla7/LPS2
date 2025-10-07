#!/usr/bin/env python
import http.server
import socketserver
import os
import sys
from pathlib import Path

PORT = 8081

# Check if necessary files exist
readme_path = Path('./README.md')
preview_html_path = Path('./readme_preview.html')

if not readme_path.exists():
    print(f"Error: {readme_path} not found!")
    sys.exit(1)

if not preview_html_path.exists():
    print(f"Error: {preview_html_path} not found!")
    sys.exit(1)

class MyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            # Redirect to the preview HTML
            self.send_response(302)
            self.send_header('Location', '/readme_preview.html')
            self.end_headers()
        else:
            return http.server.SimpleHTTPRequestHandler.do_GET(self)
            
print(f"Starting server at http://localhost:{PORT}")
print(f"Preview available at http://localhost:{PORT}/readme_preview.html")
httpd = socketserver.TCPServer(("", PORT), MyHandler)

try:
    httpd.serve_forever()
except KeyboardInterrupt:
    print("\nShutting down server...")
    httpd.shutdown()