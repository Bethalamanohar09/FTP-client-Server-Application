#!/usr/bin/env python3
"""
Simple Interactive FTP CLI Client (TCP Socket Implementation)
---------------------------------------------------------------
Computer Networks Lab Project: RFC 959 Socket Implementation
Standard Python Library only (socket, os, sys)
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
import re
import socket

HOST = "127.0.0.1"
CONTROL_PORT = 2121
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_DIR = os.path.join(BASE_DIR, "storage", "client")
os.makedirs(CLIENT_DIR, exist_ok=True)

class FTPClient:
    def __init__(self, host=HOST, port=CONTROL_PORT):
        self.host = host
        self.port = port
        self.sock = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.host, self.port))
            greeting = self.get_response()
            print(greeting)
            return True
        except Exception as e:
            print(f"[!] Connection failed to {self.host}:{self.port} -> {e}")
            return False

    def send_cmd(self, cmd):
        line = f"{cmd}\r\n"
        self.sock.sendall(line.encode("utf-8"))
        return self.get_response()

    def get_response(self):
        res = self.sock.recv(4096).decode("utf-8", errors="replace")
        return res.strip()

    def enter_pasv(self):
        """Send PASV and parse returned port."""
        resp = self.send_cmd("PASV")
        print(f"S -> C: {resp}")
        match = re.search(r"\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)", resp)
        if not match:
            print("[!] Could not parse PASV response.")
            return None
        h1, h2, h3, h4, p1, p2 = [int(x) for x in match.groups()]
        ip = f"{h1}.{h2}.{h3}.{h4}"
        port = p1 * 256 + p2
        data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        data_sock.connect((ip, port))
        return data_sock

    def do_list(self):
        data_sock = self.enter_pasv()
        if not data_sock:
            return
        resp = self.send_cmd("LIST")
        print(f"S -> C: {resp}")
        data = b""
        while True:
            chunk = data_sock.recv(4096)
            if not chunk:
                break
            data += chunk
        data_sock.close()
        print("\n--- Remote Directory Listing ---")
        print(data.decode("utf-8", errors="replace").strip())
        print("--------------------------------")
        print(f"S -> C: {self.get_response()}")

    def do_get(self, filename):
        data_sock = self.enter_pasv()
        if not data_sock:
            return
        resp = self.send_cmd(f"RETR {filename}")
        print(f"S -> C: {resp}")
        if resp.startswith("550") or resp.startswith("4"):
            data_sock.close()
            return

        dest_file = os.path.join(CLIENT_DIR, filename)
        bytes_recv = 0
        with open(dest_file, "wb") as f:
            while True:
                chunk = data_sock.recv(4096)
                if not chunk:
                    break
                f.write(chunk)
                bytes_recv += len(chunk)
        data_sock.close()
        print(f"S -> C: {self.get_response()}")
        print(f"[+] Downloaded '{filename}' ({bytes_recv} bytes) to {dest_file}")

    def do_put(self, filename):
        src_file = os.path.join(CLIENT_DIR, filename)
        if not os.path.exists(src_file):
            print(f"[!] Local client file '{filename}' not found in {CLIENT_DIR}")
            return

        data_sock = self.enter_pasv()
        if not data_sock:
            return
        resp = self.send_cmd(f"STOR {filename}")
        print(f"S -> C: {resp}")
        if resp.startswith("4") or resp.startswith("5"):
            data_sock.close()
            return

        bytes_sent = 0
        with open(src_file, "rb") as f:
            while True:
                chunk = f.read(4096)
                if not chunk:
                    break
                data_sock.sendall(chunk)
                bytes_sent += len(chunk)
        data_sock.close()
        print(f"S -> C: {self.get_response()}")
        print(f"[+] Uploaded '{filename}' ({bytes_sent} bytes) successfully.")

    def close(self):
        try:
            print(self.send_cmd("QUIT"))
            self.sock.close()
        except Exception:
            pass

def interactive_cli():
    print("=" * 60)
    print("  [+] STANDALONE PYTHON SOCKET FTP CLIENT (RFC 959)")
    print("=" * 60)
    client = FTPClient()
    if not client.connect():
        sys.exit(1)

    # Login prompt
    user = input("Username [anonymous]: ").strip() or "anonymous"
    resp = client.send_cmd(f"USER {user}")
    print(f"S -> C: {resp}")
    if resp.startswith("331"):
        pwd = input(f"Password for {user}: ").strip()
        resp = client.send_cmd(f"PASS {pwd}")
        print(f"S -> C: {resp}")

    print("\nConnected to FTP Server! Type 'help' for command list.")

    while True:
        try:
            cmd = input("ftp> ").strip()
            if not cmd:
                continue

            parts = cmd.split(None, 1)
            action = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            if action in ("exit", "quit", "bye"):
                client.close()
                print("Disconnected.")
                break
            elif action in ("ls", "dir", "list"):
                client.do_list()
            elif action == "pwd":
                print(f"S -> C: {client.send_cmd('PWD')}")
            elif action == "cd":
                target_dir = arg if arg else "/"
                print(f"S -> C: {client.send_cmd(f'CWD {target_dir}')}")
            elif action in ("get", "recv", "retr"):
                if not arg:
                    print("Usage: get <remote_filename>")
                else:
                    client.do_get(arg)
            elif action in ("put", "send", "stor"):
                if not arg:
                    print("Usage: put <local_filename>")
                else:
                    client.do_put(arg)
            elif action == "mkdir":
                if not arg:
                    print("Usage: mkdir <folder_name>")
                else:
                    print(f"S -> C: {client.send_cmd(f'MKD {arg}')}")
            elif action in ("del", "delete", "rm"):
                if not arg:
                    print("Usage: delete <filename>")
                else:
                    print(f"S -> C: {client.send_cmd(f'DELE {arg}')}")
            elif action == "help":
                print("""Available Commands:
  ls, dir              List files on remote server
  pwd                  Print current working directory on server
  cd <dir>             Change remote directory
  get <file>           Download file from server to client folder
  put <file>           Upload file from client folder to server
  mkdir <dir>          Create folder on server
  delete <file>        Delete file on server
  raw <cmd>            Send raw RFC 959 FTP command
  quit, exit           Exit session""")
            elif action == "raw":
                if arg:
                    print(f"S -> C: {client.send_cmd(arg)}")
            else:
                # Fallback to direct raw command
                print(f"S -> C: {client.send_cmd(cmd)}")
        except KeyboardInterrupt:
            print("\nExiting...")
            client.close()
            break
        except Exception as e:
            print(f"[!] Error: {e}")

if __name__ == "__main__":
    interactive_cli()
