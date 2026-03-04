# Copyright (c) 2024, RoboVerse community
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import http.server
import socketserver
import json
import os
import sys
import requests

path_to_add = os.path.abspath(os.path.join(os.path.dirname(__file__), "../python"))
if os.path.exists(path_to_add):
    sys.path.insert(0, path_to_add)
    print(f"Added {path_to_add} to sys.path")
else:
    print(f"Path {path_to_add} does not exist")

import go2_webrtc

PORT = int(os.getenv("GO2_WEBRTC_PORT", "8081"))
DEFAULT_TOKEN = os.getenv("GO2_DEFAULT_TOKEN", os.getenv("ROBOT_TOKEN", ""))
DEFAULT_ROBOT_IP = os.getenv("GO2_DEFAULT_IP", os.getenv("ROBOT_IP", ""))


def get_peer_answer_legacy(offer, token, robot_ip):
    payload = {
        "sdp": offer.sdp,
        "id": "STA_localNetwork",
        "type": offer.type,
        "token": token,
    }
    headers = {"content-type": "application/json"}
    resp = requests.post(
        f"http://{robot_ip}:8081/offer", json=payload, headers=headers, timeout=8
    )
    resp.raise_for_status()
    return resp.json()

class SDPDict:
    def __init__(self, existing_dict):
        self.__dict__["_dict"] = existing_dict

    def __getattr__(self, attr):
        try:
            return self._dict[attr]
        except KeyError:
            raise AttributeError(f"No such attribute: {attr}")


class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/defaults"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            payload = {
                "token": DEFAULT_TOKEN,
                "robot_ip": DEFAULT_ROBOT_IP,
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        super().do_GET()

    def do_OPTIONS(self):
        # Handle CORS preflight request
        self.send_response(200, "ok")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if self.path == "/offer":
            # Read the length of the data
            content_length = int(self.headers["Content-Length"])
            # Read the incoming data
            post_data = self.rfile.read(content_length)
            # Parse the JSON data
            try:
                data = SDPDict(json.loads(post_data))
            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
                return

            try:
                try:
                    response_data = go2_webrtc.Go2Connection.get_peer_answer(
                        data, data.token, data.ip
                    )
                except Exception as new_method_exc:
                    response_data = get_peer_answer_legacy(data, data.token, data.ip)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode("utf-8"))
            except Exception as exc:
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"error": f"Offer failed: {exc}"}).encode("utf-8")
                )


# Set up the server
with socketserver.TCPServer(("", PORT), CORSRequestHandler) as httpd:
    print(f"Serving on port {PORT}")
    httpd.serve_forever()


