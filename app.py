#!/usr/bin/env python3
"""
Simple FTP Client-Server Web Application & Interactive Laboratory
-----------------------------------------------------------------
Computer Networks Lab Project (RFC 959 Implementation & Visualizer)
Built with 100% Python Standard Library (Zero External Dependencies)
"""

import sys

# Ensure UTF-8 output on Windows consoles
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import http.server
import json
import mimetypes
import os
import shutil
import socket
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime

# Base Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
SERVER_STORAGE = os.path.join(BASE_DIR, "storage", "server")
CLIENT_STORAGE = os.path.join(BASE_DIR, "storage", "client")

# Ensure storage directories exist
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(SERVER_STORAGE, exist_ok=True)
os.makedirs(CLIENT_STORAGE, exist_ok=True)

# Predefined Accounts for CN Lab
USERS_DB = {
    "anonymous": "",
    "admin": "admin123",
    "student": "netlab",
    "examiner": "viva2026"
}

class FTPSessionState:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        with getattr(self, "lock", threading.Lock()):
            self.is_connected = False
            self.current_user = None
            self.authenticated = False
            self.pending_user = None
            self.mode = "PASV"  # PASV or PORT
            self.server_cwd = "/"
            self.client_cwd = "/"
            self.control_port = 21
            self.data_port = 2024
            self.session_started = None
            self.bytes_uploaded = 0
            self.bytes_downloaded = 0
            self.commands_count = 0
            self.packet_history = []
            self.max_packets = 100

    def add_packet(self, channel, direction, message, code=None, note=""):
        with self.lock:
            packet = {
                "id": len(self.packet_history) + 1,
                "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "channel": channel,  # 'CONTROL' or 'DATA'
                "port": self.control_port if channel == "CONTROL" else self.data_port,
                "direction": direction,  # 'C->S' or 'S->C'
                "message": message,
                "code": code,
                "note": note
            }
            self.packet_history.append(packet)
            if len(self.packet_history) > self.max_packets:
                self.packet_history.pop(0)
            return packet

session_state = FTPSessionState()


def get_safe_path(base_folder, relative_path):
    """Prevent directory traversal attacks."""
    cleaned = relative_path.lstrip("/\\")
    full_path = os.path.normpath(os.path.join(base_folder, cleaned))
    if not full_path.startswith(base_folder):
        return base_folder
    return full_path


def list_files_in_dir(folder_path, rel_dir="/"):
    target_dir = get_safe_path(folder_path, rel_dir)
    if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
        return []
    
    entries = []
    try:
        for item in sorted(os.listdir(target_dir)):
            full_item_path = os.path.join(target_dir, item)
            stat = os.stat(full_item_path)
            is_dir = os.path.isdir(full_item_path)
            size = 0 if is_dir else stat.st_size
            mod_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            ext = "" if is_dir else os.path.splitext(item)[1].lower()
            
            entries.append({
                "name": item,
                "is_dir": is_dir,
                "size": size,
                "size_formatted": format_bytes(size),
                "modified": mod_time,
                "extension": ext
            })
    except Exception as e:
        print(f"Error listing dir {target_dir}: {e}")
    return entries


def format_bytes(size):
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


class FTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP Server handling Web GUI and RFC 959 FTP Engine API."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            self.handle_api_get(path, urllib.parse.parse_qs(parsed.query))
        else:
            # Fall back to serving static files
            if path == "/" or path == "":
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            
            # Check content type
            content_type = self.headers.get("Content-Type", "")
            if "application/json" in content_type:
                try:
                    data = json.loads(body.decode("utf-8")) if body else {}
                except Exception:
                    data = {}
            else:
                data = {"raw_body": body}

            self.handle_api_post(path, data, content_type, body)
        else:
            self.send_error(404, "Not Found")

    def send_json(self, data, status=200):
        response_bytes = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(response_bytes)

    # ---------------- API GET ROUTES ----------------
    def handle_api_get(self, path, params):
        if path == "/api/status":
            with session_state.lock:
                status_data = {
                    "is_connected": session_state.is_connected,
                    "authenticated": session_state.authenticated,
                    "user": session_state.current_user,
                    "mode": session_state.mode,
                    "server_cwd": session_state.server_cwd,
                    "client_cwd": session_state.client_cwd,
                    "control_port": session_state.control_port,
                    "data_port": session_state.data_port,
                    "bytes_uploaded": session_state.bytes_uploaded,
                    "bytes_uploaded_fmt": format_bytes(session_state.bytes_uploaded),
                    "bytes_downloaded": session_state.bytes_downloaded,
                    "bytes_downloaded_fmt": format_bytes(session_state.bytes_downloaded),
                    "commands_count": session_state.commands_count,
                    "uptime_sec": int(time.time() - session_state.session_started) if session_state.session_started else 0,
                    "recent_packets": session_state.packet_history[-30:]
                }
            self.send_json(status_data)

        elif path == "/api/files":
            server_files = list_files_in_dir(SERVER_STORAGE, session_state.server_cwd)
            client_files = list_files_in_dir(CLIENT_STORAGE, session_state.client_cwd)
            self.send_json({
                "server": {
                    "cwd": session_state.server_cwd,
                    "files": server_files
                },
                "client": {
                    "cwd": session_state.client_cwd,
                    "files": client_files
                }
            })

        elif path == "/api/preview":
            target = params.get("target", ["server"])[0]
            filename = params.get("filename", [""])[0]
            base_dir = SERVER_STORAGE if target == "server" else CLIENT_STORAGE
            cwd = session_state.server_cwd if target == "server" else session_state.client_cwd
            
            file_path = os.path.join(get_safe_path(base_dir, cwd), filename)
            if not os.path.exists(file_path) or os.path.isdir(file_path):
                self.send_json({"error": "File not found or is a directory"}, 404)
                return

            size = os.path.getsize(file_path)
            mime_type, _ = mimetypes.guess_type(file_path)
            mime_type = mime_type or "text/plain"

            # Limit preview size to 256KB for text
            if mime_type.startswith("text/") or filename.endswith((".py", ".json", ".md", ".txt", ".csv", ".html", ".css", ".js")):
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read(250000)
                    self.send_json({
                        "filename": filename,
                        "type": "text",
                        "size": size,
                        "content": content
                    })
                except Exception as e:
                    self.send_json({"error": str(e)}, 500)
            elif mime_type.startswith("image/"):
                import base64
                try:
                    with open(file_path, "rb") as f:
                        b64 = base64.b64encode(f.read(2000000)).decode("utf-8")
                    self.send_json({
                        "filename": filename,
                        "type": "image",
                        "mime": mime_type,
                        "size": size,
                        "content": f"data:{mime_type};base64,{b64}"
                    })
                except Exception as e:
                    self.send_json({"error": str(e)}, 500)
            else:
                self.send_json({
                    "filename": filename,
                    "type": "binary",
                    "size": size,
                    "content": f"Binary file ({format_bytes(size)}). Preview unavailable."
                })

        elif path == "/api/download_browser":
            # Direct HTTP download of file to browser
            target = params.get("target", ["server"])[0]
            filename = params.get("filename", [""])[0]
            base_dir = SERVER_STORAGE if target == "server" else CLIENT_STORAGE
            cwd = session_state.server_cwd if target == "server" else session_state.client_cwd
            file_path = os.path.join(get_safe_path(base_dir, cwd), filename)

            if not os.path.exists(file_path) or os.path.isdir(file_path):
                self.send_error(404, "File not found")
                return

            with open(file_path, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        else:
            self.send_json({"error": "Unknown API endpoint"}, 404)

    # ---------------- API POST ROUTES ----------------
    def handle_api_post(self, path, data, content_type="", raw_body=b""):
        if path == "/api/connect":
            user = data.get("user", "anonymous").strip()
            password = data.get("password", "").strip()

            session_state.session_started = time.time()
            session_state.is_connected = True
            
            # Step 1: Server sends 220 banner
            session_state.add_packet("CONTROL", "S->C", "220 Simple FTP Server ready (RFC 959 compliant).", 220, "Server greeting")
            time.sleep(0.05)

            # Step 2: Client sends USER
            session_state.add_packet("CONTROL", "C->S", f"USER {user}", None, "Authentication request")
            time.sleep(0.05)

            if user not in USERS_DB:
                session_state.add_packet("CONTROL", "S->C", "530 Not logged in. User unknown.", 530, "Authentication failed")
                self.send_json({
                    "success": False,
                    "code": 530,
                    "message": "530 Not logged in. User unknown."
                })
                return

            # Check if password needed
            expected_pwd = USERS_DB[user]
            if expected_pwd:
                session_state.pending_user = user
                session_state.add_packet("CONTROL", "S->C", f"331 Password required for {user}.", 331, "Password required")
                time.sleep(0.05)
                
                # Check password
                session_state.add_packet("CONTROL", "C->S", f"PASS {'*' * len(password)}", None, "Password submitted")
                time.sleep(0.05)
                
                if password != expected_pwd:
                    session_state.add_packet("CONTROL", "S->C", "530 Login incorrect.", 530, "Incorrect password")
                    self.send_json({
                        "success": False,
                        "code": 530,
                        "message": "530 Login incorrect. Authentication failed."
                    })
                    return

            # Logged in successfully
            session_state.authenticated = True
            session_state.current_user = user
            session_state.add_packet("CONTROL", "S->C", f"230 User {user} logged in, proceed.", 230, "Session established")
            
            self.send_json({
                "success": True,
                "code": 230,
                "user": user,
                "message": f"230 User {user} logged in successfully."
            })

        elif path == "/api/disconnect":
            session_state.add_packet("CONTROL", "C->S", "QUIT", None, "Client terminating session")
            session_state.add_packet("CONTROL", "S->C", "221 Goodbye. Closing control connection.", 221, "Session closed")
            session_state.reset()
            self.send_json({"success": True, "code": 221, "message": "221 Service closing control connection."})

        elif path == "/api/command":
            raw_cmd = data.get("command", "").strip()
            if not raw_cmd:
                self.send_json({"error": "Empty command"}, 400)
                return
            response = self.execute_ftp_command(raw_cmd)
            self.send_json(response)

        elif path == "/api/transfer":
            # Simulate FTP STOR or RETR between Client storage and Server storage
            direction = data.get("direction", "upload")  # "upload" (STOR) or "download" (RETR)
            filename = data.get("filename", "").strip()
            
            if not session_state.authenticated:
                self.send_json({"success": False, "code": 530, "message": "530 Please login with USER and PASS first."}, 401)
                return

            if not filename:
                self.send_json({"success": False, "message": "Filename required"}, 400)
                return

            if direction == "upload":
                # STOR from Client storage to Server storage
                src_path = os.path.join(get_safe_path(CLIENT_STORAGE, session_state.client_cwd), filename)
                dst_dir = get_safe_path(SERVER_STORAGE, session_state.server_cwd)
                dst_path = os.path.join(dst_dir, filename)

                if not os.path.exists(src_path):
                    self.send_json({"success": False, "message": f"Source file '{filename}' not found in client folder."}, 404)
                    return

                file_size = os.path.getsize(src_path)
                
                # 1. Establish Data Connection (PASV / PORT)
                mode_str = f"227 Entering Passive Mode (127,0,0,1,7,232)" if session_state.mode == "PASV" else "200 PORT command successful"
                session_state.add_packet("CONTROL", "S->C", mode_str, 227 if session_state.mode == "PASV" else 200, "Data connection setup")
                
                # 2. Command STOR
                session_state.add_packet("CONTROL", "C->S", f"STOR {filename}", None, "Store file command")
                session_state.add_packet("CONTROL", "S->C", f"150 Opening BINARY mode data connection for {filename} ({file_size} bytes).", 150, "Data transfer initiated")
                
                # 3. Simulate binary packet chunk transmission on Data Port
                chunks = max(1, min(5, file_size // 1024 or 1))
                for i in range(chunks):
                    pct = int(((i + 1) / chunks) * 100)
                    session_state.add_packet("DATA", "C->S", f"[DATA PACKET #{i+1}] {file_size // chunks} bytes transferred ({pct}%)", None, f"TCP Data Stream Port {session_state.data_port}")

                shutil.copy2(src_path, dst_path)
                session_state.bytes_uploaded += file_size
                
                # 4. Transfer Complete
                session_state.add_packet("CONTROL", "S->C", "226 Transfer complete. Closing data connection.", 226, "Transfer succeeded")
                
                self.send_json({
                    "success": True,
                    "code": 226,
                    "direction": "STOR",
                    "filename": filename,
                    "bytes": file_size,
                    "message": f"226 Transfer complete ({file_size} bytes transferred via data connection)."
                })

            else:
                # RETR from Server storage to Client storage
                src_path = os.path.join(get_safe_path(SERVER_STORAGE, session_state.server_cwd), filename)
                dst_dir = get_safe_path(CLIENT_STORAGE, session_state.client_cwd)
                dst_path = os.path.join(dst_dir, filename)

                if not os.path.exists(src_path):
                    session_state.add_packet("CONTROL", "C->S", f"RETR {filename}", None, "Retrieve file command")
                    session_state.add_packet("CONTROL", "S->C", f"550 {filename}: No such file or directory.", 550, "File error")
                    self.send_json({"success": False, "code": 550, "message": f"550 {filename}: File not found."}, 404)
                    return

                file_size = os.path.getsize(src_path)
                
                # 1. PASV mode negotiation
                mode_str = f"227 Entering Passive Mode (127,0,0,1,7,232)" if session_state.mode == "PASV" else "200 PORT command successful"
                session_state.add_packet("CONTROL", "S->C", mode_str, 227 if session_state.mode == "PASV" else 200, "Data connection setup")

                # 2. Command RETR
                session_state.add_packet("CONTROL", "C->S", f"RETR {filename}", None, "Retrieve file command")
                session_state.add_packet("CONTROL", "S->C", f"150 Opening BINARY mode data connection for {filename} ({file_size} bytes).", 150, "Data transfer initiated")
                
                # 3. Simulate binary packet chunk transmission on Data Port
                chunks = max(1, min(5, file_size // 1024 or 1))
                for i in range(chunks):
                    pct = int(((i + 1) / chunks) * 100)
                    session_state.add_packet("DATA", "S->C", f"[DATA PACKET #{i+1}] {file_size // chunks} bytes transferred ({pct}%)", None, f"TCP Data Stream Port {session_state.data_port}")

                shutil.copy2(src_path, dst_path)
                session_state.bytes_downloaded += file_size
                
                # 4. Transfer Complete
                session_state.add_packet("CONTROL", "S->C", "226 Transfer complete. Closing data connection.", 226, "Transfer succeeded")

                self.send_json({
                    "success": True,
                    "code": 226,
                    "direction": "RETR",
                    "filename": filename,
                    "bytes": file_size,
                    "message": f"226 Transfer complete ({file_size} bytes received via data connection)."
                })

        elif path == "/api/upload_file":
            # Direct upload from user's physical browser into client or server folder
            target = data.get("target", "client")
            filename = data.get("filename", "upload.txt")
            file_content = data.get("content", "")
            
            base_folder = SERVER_STORAGE if target == "server" else CLIENT_STORAGE
            cwd = session_state.server_cwd if target == "server" else session_state.client_cwd
            dest_dir = get_safe_path(base_folder, cwd)
            dest_path = os.path.join(dest_dir, filename)

            try:
                if isinstance(file_content, str):
                    if file_content.startswith("data:") and ";base64," in file_content:
                        import base64
                        raw_data = base64.b64decode(file_content.split(";base64,")[1])
                        with open(dest_path, "wb") as f:
                            f.write(raw_data)
                        fsize = len(raw_data)
                    else:
                        with open(dest_path, "w", encoding="utf-8") as f:
                            f.write(file_content)
                        fsize = len(file_content.encode("utf-8"))
                else:
                    with open(dest_path, "wb") as f:
                        f.write(file_content)
                    fsize = len(file_content)

                if target == "server":
                    session_state.bytes_uploaded += fsize
                    session_state.add_packet("DATA", "C->S", f"[STOR FILE] {filename} ({fsize} bytes)", None, "Direct file stored")
                
                self.send_json({"success": True, "filename": filename, "size": fsize})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 500)

        elif path == "/api/mkdir":
            target = data.get("target", "server")
            dirname = data.get("dirname", "").strip()
            if not dirname:
                self.send_json({"error": "Folder name required"}, 400)
                return
            
            base_folder = SERVER_STORAGE if target == "server" else CLIENT_STORAGE
            cwd = session_state.server_cwd if target == "server" else session_state.client_cwd
            target_path = os.path.join(get_safe_path(base_folder, cwd), dirname)
            
            try:
                os.makedirs(target_path, exist_ok=True)
                if target == "server":
                    session_state.add_packet("CONTROL", "C->S", f"MKD {dirname}", None, "Create directory")
                    session_state.add_packet("CONTROL", "S->C", f'257 "{dirname}" created successfully.', 257, "Directory created")
                self.send_json({"success": True, "message": f'Directory "{dirname}" created.'})
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        elif path == "/api/delete":
            target = data.get("target", "server")
            filename = data.get("filename", "").strip()
            if not filename:
                self.send_json({"error": "Item name required"}, 400)
                return

            base_folder = SERVER_STORAGE if target == "server" else CLIENT_STORAGE
            cwd = session_state.server_cwd if target == "server" else session_state.client_cwd
            target_path = os.path.join(get_safe_path(base_folder, cwd), filename)

            try:
                if os.path.isdir(target_path):
                    shutil.rmtree(target_path)
                    msg = f"Directory {filename} removed."
                    code = 250
                    cmd = f"RMD {filename}"
                else:
                    os.remove(target_path)
                    msg = f"File {filename} deleted."
                    code = 250
                    cmd = f"DELE {filename}"

                if target == "server":
                    session_state.add_packet("CONTROL", "C->S", cmd, None, "Delete command")
                    session_state.add_packet("CONTROL", "S->C", f"{code} {msg}", code, "Deletion successful")
                
                self.send_json({"success": True, "message": msg})
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        elif path == "/api/navigate":
            target = data.get("target", "server")
            directory = data.get("directory", "/").strip()
            
            base_folder = SERVER_STORAGE if target == "server" else CLIENT_STORAGE
            current_cwd = session_state.server_cwd if target == "server" else session_state.client_cwd

            if directory == "..":
                new_cwd = os.path.dirname(current_cwd.rstrip("/")) or "/"
            elif directory.startswith("/"):
                new_cwd = directory
            else:
                new_cwd = os.path.normpath(os.path.join(current_cwd, directory)).replace("\\", "/")

            # Validate exists
            resolved = get_safe_path(base_folder, new_cwd)
            if not os.path.exists(resolved) or not os.path.isdir(resolved):
                self.send_json({"success": False, "message": "Directory does not exist"}, 404)
                return

            if target == "server":
                session_state.server_cwd = new_cwd
                session_state.add_packet("CONTROL", "C->S", f"CWD {directory}", None, "Change directory")
                session_state.add_packet("CONTROL", "S->C", f'250 Directory changed to "{new_cwd}".', 250, "CWD Success")
            else:
                session_state.client_cwd = new_cwd

            self.send_json({"success": True, "cwd": new_cwd})

        elif path == "/api/reset_demo":
            # Reset sample environment
            self.reset_sample_files()
            session_state.reset()
            self.send_json({"success": True, "message": "Demo environment reset successfully."})

        else:
            self.send_json({"error": "Unknown API endpoint"}, 404)

    def execute_ftp_command(self, raw_cmd):
        """RFC 959 FTP Command Engine with Official Reply Codes."""
        parts = raw_cmd.split(None, 1)
        verb = parts[0].upper()
        arg = parts[1].strip() if len(parts) > 1 else ""

        session_state.commands_count += 1
        session_state.add_packet("CONTROL", "C->S", raw_cmd, None, f"Command {verb}")

        # Commands allowed prior to authentication
        if verb == "USER":
            if not session_state.is_connected:
                session_state.is_connected = True
                session_state.session_started = time.time()
                session_state.add_packet("CONTROL", "S->C", "220 Simple FTP Server Ready.", 220, "Server greeting")
            
            if arg not in USERS_DB:
                msg = f"530 User '{arg}' unknown."
                session_state.add_packet("CONTROL", "S->C", msg, 530, "User invalid")
                return {"code": 530, "message": msg, "success": False}

            session_state.pending_user = arg
            if USERS_DB[arg]:
                msg = f"331 Password required for {arg}."
                session_state.add_packet("CONTROL", "S->C", msg, 331, "Password required")
                return {"code": 331, "message": msg, "success": True, "pending_user": arg}
            else:
                session_state.authenticated = True
                session_state.current_user = arg
                msg = f"230 User {arg} logged in."
                session_state.add_packet("CONTROL", "S->C", msg, 230, "Authentication success")
                return {"code": 230, "message": msg, "success": True, "user": arg}

        elif verb == "PASS":
            if not session_state.pending_user:
                msg = "503 Bad sequence of commands. Send USER first."
                session_state.add_packet("CONTROL", "S->C", msg, 503, "Sequence error")
                return {"code": 503, "message": msg, "success": False}

            expected = USERS_DB.get(session_state.pending_user, "")
            if arg == expected:
                session_state.authenticated = True
                session_state.current_user = session_state.pending_user
                session_state.pending_user = None
                msg = f"230 User {session_state.current_user} logged in, proceed."
                session_state.add_packet("CONTROL", "S->C", msg, 230, "Login complete")
                return {"code": 230, "message": msg, "success": True, "user": session_state.current_user}
            else:
                msg = "530 Login incorrect."
                session_state.add_packet("CONTROL", "S->C", msg, 530, "Password mismatch")
                return {"code": 530, "message": msg, "success": False}

        elif verb == "QUIT":
            msg = "221 Goodbye. Service closing control connection."
            session_state.add_packet("CONTROL", "S->C", msg, 221, "Connection closing")
            session_state.reset()
            return {"code": 221, "message": msg, "success": True}

        elif verb == "HELP":
            supported = ["USER", "PASS", "LIST", "NLST", "PWD", "CWD", "CDUP", "MKD", "RMD", "DELE", "SIZE", "TYPE", "PASV", "PORT", "SYST", "NOOP", "HELP", "QUIT"]
            msg = "214-The following commands are recognized:\r\n   " + " ".join(supported) + "\r\n214 Help command successful."
            session_state.add_packet("CONTROL", "S->C", msg, 214, "Help response")
            return {"code": 214, "message": msg, "success": True, "commands": supported}

        elif verb == "SYST":
            msg = "215 UNIX Type: L8 (Simulated RFC 959 Server)"
            session_state.add_packet("CONTROL", "S->C", msg, 215, "System type")
            return {"code": 215, "message": msg, "success": True}

        elif verb == "NOOP":
            msg = "200 NOOP command successful."
            session_state.add_packet("CONTROL", "S->C", msg, 200, "Keepalive OK")
            return {"code": 200, "message": msg, "success": True}

        # Check authentication for remaining commands
        if not session_state.authenticated:
            msg = "530 Please login with USER and PASS."
            session_state.add_packet("CONTROL", "S->C", msg, 530, "Unauthorized")
            return {"code": 530, "message": msg, "success": False}

        if verb == "PWD":
            msg = f'257 "{session_state.server_cwd}" is the current directory.'
            session_state.add_packet("CONTROL", "S->C", msg, 257, "Print working directory")
            return {"code": 257, "message": msg, "success": True, "cwd": session_state.server_cwd}

        elif verb in ("CWD", "CDUP"):
            target_dir = ".." if verb == "CDUP" else (arg or "/")
            if target_dir == "..":
                new_cwd = os.path.dirname(session_state.server_cwd.rstrip("/")) or "/"
            elif target_dir.startswith("/"):
                new_cwd = target_dir
            else:
                new_cwd = os.path.normpath(os.path.join(session_state.server_cwd, target_dir)).replace("\\", "/")

            real_path = get_safe_path(SERVER_STORAGE, new_cwd)
            if not os.path.exists(real_path) or not os.path.isdir(real_path):
                msg = f"550 {target_dir}: No such file or directory."
                session_state.add_packet("CONTROL", "S->C", msg, 550, "CWD Failed")
                return {"code": 550, "message": msg, "success": False}

            session_state.server_cwd = new_cwd
            msg = f'250 Directory successfully changed to "{new_cwd}".'
            session_state.add_packet("CONTROL", "S->C", msg, 250, "CWD Success")
            return {"code": 250, "message": msg, "success": True, "cwd": new_cwd}

        elif verb in ("LIST", "NLST"):
            session_state.add_packet("CONTROL", "S->C", "150 Here comes the directory listing.", 150, "Opening data channel")
            files = list_files_in_dir(SERVER_STORAGE, session_state.server_cwd)
            listing_lines = []
            for f in files:
                prefix = "drwxr-xr-x 1 owner group" if f["is_dir"] else "-rw-r--r-- 1 owner group"
                listing_lines.append(f"{prefix} {f['size']:>8} {f['modified']} {f['name']}")
            
            listing_text = "\r\n".join(listing_lines)
            session_state.add_packet("DATA", "S->C", f"[DIRECTORY LISTING]\r\n{listing_text}", None, "Directory data via port 20")
            msg = "226 Directory send OK."
            session_state.add_packet("CONTROL", "S->C", msg, 226, "Transfer complete")
            return {"code": 226, "message": msg, "listing": listing_lines, "files": files, "success": True}

        elif verb == "TYPE":
            type_mode = arg.upper()
            if type_mode in ("I", "IMAGE", "A", "ASCII"):
                mode_desc = "Binary" if type_mode in ("I", "IMAGE") else "ASCII"
                msg = f"200 Type set to {mode_desc}."
                session_state.add_packet("CONTROL", "S->C", msg, 200, "Representation type set")
                return {"code": 200, "message": msg, "success": True}
            else:
                msg = f"504 Command not implemented for that parameter: {arg}"
                session_state.add_packet("CONTROL", "S->C", msg, 504, "Invalid type")
                return {"code": 504, "message": msg, "success": False}

        elif verb == "PASV":
            session_state.mode = "PASV"
            msg = "227 Entering Passive Mode (127,0,0,1,7,232)"  # Port 2024 = 7*256 + 232
            session_state.add_packet("CONTROL", "S->C", msg, 227, "Passive mode address/port announced")
            return {"code": 227, "message": msg, "success": True, "mode": "PASV"}

        elif verb == "PORT":
            session_state.mode = "PORT"
            msg = "200 PORT command successful. Active mode initiated."
            session_state.add_packet("CONTROL", "S->C", msg, 200, "Active mode confirmed")
            return {"code": 200, "message": msg, "success": True, "mode": "PORT"}

        elif verb == "SIZE":
            real_path = os.path.join(get_safe_path(SERVER_STORAGE, session_state.server_cwd), arg)
            if os.path.exists(real_path) and not os.path.isdir(real_path):
                size = os.path.getsize(real_path)
                msg = f"213 {size}"
                session_state.add_packet("CONTROL", "S->C", msg, 213, f"Size of {arg} is {size} bytes")
                return {"code": 213, "message": msg, "size": size, "success": True}
            else:
                msg = f"550 Could not get file size for {arg}."
                session_state.add_packet("CONTROL", "S->C", msg, 550, "File not found")
                return {"code": 550, "message": msg, "success": False}

        elif verb == "MKD":
            if not arg:
                msg = "501 Syntax error in parameters or arguments."
                session_state.add_packet("CONTROL", "S->C", msg, 501, "Missing dirname")
                return {"code": 501, "message": msg, "success": False}
            real_path = os.path.join(get_safe_path(SERVER_STORAGE, session_state.server_cwd), arg)
            try:
                os.makedirs(real_path, exist_ok=True)
                msg = f'257 "{arg}" directory created.'
                session_state.add_packet("CONTROL", "S->C", msg, 257, "MKD successful")
                return {"code": 257, "message": msg, "success": True}
            except Exception as e:
                msg = f"550 Create directory failed: {e}"
                session_state.add_packet("CONTROL", "S->C", msg, 550, "MKD failed")
                return {"code": 550, "message": msg, "success": False}

        elif verb in ("DELE", "RMD"):
            if not arg:
                msg = "501 Syntax error in parameters."
                return {"code": 501, "message": msg, "success": False}
            real_path = os.path.join(get_safe_path(SERVER_STORAGE, session_state.server_cwd), arg)
            if not os.path.exists(real_path):
                msg = f"550 {arg}: File or directory not found."
                session_state.add_packet("CONTROL", "S->C", msg, 550, "Not found")
                return {"code": 550, "message": msg, "success": False}
            try:
                if os.path.isdir(real_path):
                    shutil.rmtree(real_path)
                    msg = f"250 Directory '{arg}' removed successfully."
                else:
                    os.remove(real_path)
                    msg = f"250 File '{arg}' deleted successfully."
                session_state.add_packet("CONTROL", "S->C", msg, 250, "Delete successful")
                return {"code": 250, "message": msg, "success": True}
            except Exception as e:
                msg = f"550 Delete operation failed: {e}"
                session_state.add_packet("CONTROL", "S->C", msg, 550, "Delete failed")
                return {"code": 550, "message": msg, "success": False}

        else:
            msg = f"500 Unknown command '{verb}'. Type HELP for supported commands."
            session_state.add_packet("CONTROL", "S->C", msg, 500, "Unknown command")
            return {"code": 500, "message": msg, "success": False}

    def reset_sample_files(self):
        """Populate initial sample files in server and client."""
        # Server sample files
        with open(os.path.join(SERVER_STORAGE, "welcome_server.txt"), "w") as f:
            f.write("Welcome to the Computer Networks Lab FTP Server!\nRFC 959 File Transfer Protocol Demo.\nControl Port: 21, Data Port: 20.\n")
        with open(os.path.join(SERVER_STORAGE, "network_notes.md"), "w") as f:
            f.write("# Computer Networks Lab\n## Topic: File Transfer Protocol (FTP)\n- Dual Connection Architecture\n- RFC 959 Standards\n- Active vs Passive Data Connections\n")
        
        # Client sample files
        with open(os.path.join(CLIENT_STORAGE, "lab_report.txt"), "w") as f:
            f.write("Student CN Lab Report:\nExperiment 4: FTP Client-Server Implementation\nTesting STOR and RETR commands.\nStatus: Verified\n")
        with open(os.path.join(CLIENT_STORAGE, "network_config.json"), "w") as f:
            f.write('{\n  "client_ip": "127.0.0.1",\n  "mode": "PASV",\n  "status": "ready"\n}\n')


def find_free_port(preferred_port=5000):
    env_port = os.environ.get("PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass
    for port in [preferred_port, 5050, 8080, 8000, 8888, 3000]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return 5000


def run_web_server(port=5000, host="0.0.0.0"):
    handler = FTPRequestHandler
    server = http.server.ThreadingHTTPServer((host, port), handler)
    display_host = "127.0.0.1" if host == "0.0.0.0" else host
    print("=" * 65)
    print("  [+] CN LAB PROJECT: SIMPLE FTP CLIENT-SERVER APPLICATION")
    print("=" * 65)
    print(f"  [*] Web Application running at: http://{display_host}:{port}")
    print(f"  [*] Server Storage Directory:   {SERVER_STORAGE}")
    print(f"  [*] Client Storage Directory:   {CLIENT_STORAGE}")
    print("  [*] Pre-configured Accounts:")
    print("      - Anonymous: user='anonymous', password='' (empty)")
    print("      - Admin:     user='admin',     password='admin123'")
    print("      - Student:   user='student',   password='netlab'")
    print("=" * 65)
    print("  Press Ctrl+C to terminate the server.\n")

    # Only auto-open browser in local desktop environments (not on Render/cloud)
    is_cloud = os.environ.get("RENDER") or os.environ.get("CI") or os.environ.get("PORT")
    if not is_cloud:
        def open_browser():
            time.sleep(1.2)
            try:
                webbrowser.open(f"http://127.0.0.1:{port}")
            except Exception:
                pass

        threading.Thread(target=open_browser, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Shutting down FTP web application. Goodbye!")
        server.server_close()


if __name__ == "__main__":
    target_host = os.environ.get("HOST", "0.0.0.0")
    target_port = find_free_port(5000)
    run_web_server(target_port, target_host)
