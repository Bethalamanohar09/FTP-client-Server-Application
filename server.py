#!/usr/bin/env python3
"""
Simple Multithreaded FTP Server (TCP Socket Implementation)
------------------------------------------------------------
Computer Networks Lab Project: RFC 959 Socket Implementation
Standard Python Library only (socket, threading, os, sys)
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

import os
import socket
import threading
import time

HOST = "127.0.0.1"
CONTROL_PORT = 2121  # Standard unprivileged alternative for Port 21
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "storage", "server")
os.makedirs(STORAGE_DIR, exist_ok=True)

# Lab accounts
USERS = {
    "anonymous": "",
    "admin": "admin123",
    "student": "netlab"
}

def get_safe_path(rel_path):
    cleaned = rel_path.lstrip("/\\")
    full = os.path.normpath(os.path.join(STORAGE_DIR, cleaned))
    if not full.startswith(STORAGE_DIR):
        return STORAGE_DIR
    return full

class FTPClientHandler(threading.Thread):
    def __init__(self, conn, addr):
        super().__init__(daemon=True)
        self.conn = conn
        self.addr = addr
        self.user = None
        self.authenticated = False
        self.cwd = "/"
        self.pasv_sock = None
        self.data_sock = None

    def send_resp(self, code, message):
        line = f"{code} {message}\r\n"
        print(f"[{self.addr[0]}:{self.addr[1]}] S -> C: {code} {message}")
        self.conn.sendall(line.encode("utf-8"))

    def run(self):
        print(f"[+] Client connected from {self.addr[0]}:{self.addr[1]} on Control Port {CONTROL_PORT}")
        self.send_resp(220, "Simple FTP Server (RFC 959 Lab Edition) Ready.")

        buffer = ""
        while True:
            try:
                data = self.conn.recv(1024).decode("utf-8", errors="replace")
                if not data:
                    break
                buffer += data
                while "\r\n" in buffer or "\n" in buffer:
                    if "\r\n" in buffer:
                        cmd_line, buffer = buffer.split("\r\n", 1)
                    else:
                        cmd_line, buffer = buffer.split("\n", 1)
                    
                    cmd_line = cmd_line.strip()
                    if not cmd_line:
                        continue
                    
                    print(f"[{self.addr[0]}:{self.addr[1]}] C -> S: {cmd_line}")
                    if not self.handle_command(cmd_line):
                        return
            except ConnectionResetError:
                break
            except Exception as e:
                print(f"[!] Error in client session: {e}")
                break

        print(f"[-] Client {self.addr[0]}:{self.addr[1]} disconnected.")
        self.conn.close()

    def open_data_connection(self):
        """Accept incoming data socket from passive listener."""
        if self.pasv_sock:
            try:
                data_conn, data_addr = self.pasv_sock.accept()
                print(f"[*] Data Connection established with {data_addr[0]}:{data_addr[1]}")
                return data_conn
            except Exception as e:
                print(f"[!] Data connection error: {e}")
            finally:
                self.pasv_sock.close()
                self.pasv_sock = None
        return None

    def handle_command(self, cmd_line):
        parts = cmd_line.split(None, 1)
        verb = parts[0].upper()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if verb == "USER":
            if arg in USERS:
                self.user = arg
                if USERS[arg] == "":
                    self.authenticated = True
                    self.send_resp(230, f"User {arg} logged in successfully.")
                else:
                    self.send_resp(331, f"Password required for {arg}.")
            else:
                self.send_resp(530, f"User {arg} unknown.")

        elif verb == "PASS":
            if not self.user:
                self.send_resp(503, "Login with USER first.")
            elif USERS.get(self.user) == arg:
                self.authenticated = True
                self.send_resp(230, "User logged in, proceed.")
            else:
                self.send_resp(530, "Login incorrect.")

        elif verb == "QUIT":
            self.send_resp(221, "Goodbye. Closing control connection.")
            return False

        elif verb == "NOOP":
            self.send_resp(200, "NOOP OK.")

        elif verb == "HELP":
            self.send_resp(214, "Supported: USER, PASS, PWD, CWD, LIST, PASV, RETR, STOR, DELE, MKD, QUIT, HELP")

        # Commands requiring authentication
        elif not self.authenticated:
            self.send_resp(530, "Please login with USER and PASS.")

        elif verb == "PWD":
            self.send_resp(257, f'"{self.cwd}" is the current directory.')

        elif verb in ("CWD", "CDUP"):
            target = ".." if verb == "CDUP" else (arg or "/")
            new_cwd = os.path.dirname(self.cwd.rstrip("/")) or "/" if target == ".." else os.path.normpath(os.path.join(self.cwd, target)).replace("\\", "/")
            real_path = get_safe_path(new_cwd)
            if os.path.exists(real_path) and os.path.isdir(real_path):
                self.cwd = new_cwd
                self.send_resp(250, f'Directory changed to "{new_cwd}".')
            else:
                self.send_resp(550, f"Failed to change directory to {target}.")

        elif verb == "PASV":
            if self.pasv_sock:
                self.pasv_sock.close()
            self.pasv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.pasv_sock.bind((HOST, 0))
            self.pasv_sock.listen(1)
            port = self.pasv_sock.getsockname()[1]
            p1 = port // 256
            p2 = port % 256
            ip_parts = HOST.replace(".", ",")
            self.send_resp(227, f"Entering Passive Mode ({ip_parts},{p1},{p2})")

        elif verb in ("LIST", "NLST"):
            self.send_resp(150, "Here comes the directory listing.")
            data_conn = self.open_data_connection()
            if data_conn:
                try:
                    real_path = get_safe_path(self.cwd)
                    lines = []
                    for item in os.listdir(real_path):
                        fpath = os.path.join(real_path, item)
                        is_dir = os.path.isdir(fpath)
                        fsize = os.path.getsize(fpath) if not is_dir else 0
                        mode = "drwxr-xr-x" if is_dir else "-rw-r--r--"
                        lines.append(f"{mode} 1 owner group {fsize:>8} {item}\r\n")
                    data_conn.sendall("".join(lines).encode("utf-8"))
                finally:
                    data_conn.close()
                self.send_resp(226, "Directory send OK.")
            else:
                self.send_resp(425, "Can't open data connection.")

        elif verb == "RETR":
            real_path = os.path.join(get_safe_path(self.cwd), arg)
            if not os.path.exists(real_path) or os.path.isdir(real_path):
                self.send_resp(550, f"File {arg} not found.")
            else:
                fsize = os.path.getsize(real_path)
                self.send_resp(150, f"Opening BINARY mode data connection for {arg} ({fsize} bytes).")
                data_conn = self.open_data_connection()
                if data_conn:
                    try:
                        with open(real_path, "rb") as f:
                            while True:
                                chunk = f.read(4096)
                                if not chunk:
                                    break
                                data_conn.sendall(chunk)
                        self.send_resp(226, "Transfer complete.")
                    finally:
                        data_conn.close()
                else:
                    self.send_resp(425, "Can't open data connection.")

        elif verb == "STOR":
            real_path = os.path.join(get_safe_path(self.cwd), arg)
            self.send_resp(150, f"Ok to send data for {arg}.")
            data_conn = self.open_data_connection()
            if data_conn:
                try:
                    with open(real_path, "wb") as f:
                        while True:
                            chunk = data_conn.recv(4096)
                            if not chunk:
                                break
                            f.write(chunk)
                    self.send_resp(226, "Transfer complete.")
                finally:
                    data_conn.close()
            else:
                self.send_resp(425, "Can't open data connection.")

        elif verb in ("DELE", "RMD"):
            real_path = os.path.join(get_safe_path(self.cwd), arg)
            if not os.path.exists(real_path):
                self.send_resp(550, f"Item {arg} not found.")
            else:
                try:
                    if os.path.isdir(real_path):
                        os.rmdir(real_path)
                    else:
                        os.remove(real_path)
                    self.send_resp(250, f"{arg} deleted successfully.")
                except Exception as e:
                    self.send_resp(550, f"Delete failed: {e}")

        elif verb == "MKD":
            real_path = os.path.join(get_safe_path(self.cwd), arg)
            try:
                os.makedirs(real_path, exist_ok=True)
                self.send_resp(257, f'"{arg}" created.')
            except Exception as e:
                self.send_resp(550, f"MKD failed: {e}")

        else:
            self.send_resp(500, f"Unknown command {verb}.")

        return True

def start_server():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_sock.bind((HOST, CONTROL_PORT))
    except Exception as e:
        print(f"[!] Could not bind to port {CONTROL_PORT}: {e}")
        return
    server_sock.listen(5)
    print("=" * 60)
    print("  [+] STANDALONE PYTHON SOCKET FTP SERVER (RFC 959)")
    print("=" * 60)
    print(f"  Listening on: {HOST}:{CONTROL_PORT}")
    print(f"  Storage root: {STORAGE_DIR}")
    print("  Press Ctrl+C to stop.")
    print("=" * 60)

    try:
        while True:
            conn, addr = server_sock.accept()
            handler = FTPClientHandler(conn, addr)
            handler.start()
    except KeyboardInterrupt:
        print("\n[!] Server stopped.")
    finally:
        server_sock.close()

if __name__ == "__main__":
    start_server()
