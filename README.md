# Computer Networks Lab Project: Simple FTP Client–Server Application

A modern, interactive, and RFC 959-compliant **File Transfer Protocol (FTP) Client–Server Application** with an animated web interface and standalone Python socket programs.

Developed with **100% Python Standard Library** (`socket`, `http.server`, `threading`, `json`) — requiring **zero external dependencies** and running out-of-the-box on any system with Python 3.

---

## 🌟 Key Highlights & Features

1. **Dual-Channel Architecture (RFC 959)**:
   - **Control Connection (Port 21)**: Dedicated to control commands (`USER`, `PASS`, `PWD`, `CWD`, `QUIT`) with official 3-digit reply codes.
   - **Data Connection (Port 20 / PASV)**: Opened dynamically on-demand for directory listings (`LIST`) and file transfers (`STOR`, `RETR`).
2. **Interactive Visual Web Workbench**:
   - **Real-Time Packet Flow Visualizer**: Live animated packet pulses along the Control (Port 21) and Data (Port 20) wires.
   - **Dual-Pane File Manager**: Side-by-side view of Local Client storage and Remote Server storage.
   - **1-Click File Transfers**: Intuitive `STOR` (upload) and `RETR` (download) buttons.
   - **Interactive Terminal & RFC 959 Protocol Sniffer**: Run raw FTP commands (`USER`, `PASS`, `LIST`, `PWD`, `PASV`, `PORT`, `HELP`) with color-coded response codes.
   - **File Previews & Drag-and-Drop**: Preview text and images right inside the browser; drag-and-drop local files for instant testing.
   - **Built-in CN Lab Viva Guide**: On-screen study guide explaining active vs passive modes, reply codes, and common viva questions.
3. **Standalone Academic Socket Scripts**:
   - `server.py`: Pure multithreaded Python TCP socket FTP server for terminal demonstrations.
   - `client.py`: Pure Python TCP socket CLI client with interactive `ftp>` prompt.

---

## 🚀 Quick Start Guide

### Option 1: Running the Interactive Web Application (Recommended)

Simply run:
```bash
python app.py
```

- Opens automatically at **`http://127.0.0.1:5000`** in your default web browser.
- Displays the full visualizer, dual file managers, and live protocol console.

### Option 2: Running the Standalone Academic Socket Programs

For demonstrating socket programming in two terminal windows:

**Terminal 1 (Start Server):**
```bash
python server.py
```
*Listens for incoming TCP connections on `127.0.0.1:2121`.*

**Terminal 2 (Start Client):**
```bash
python client.py
```
*Connects over raw sockets and launches the interactive `ftp>` shell.*

### Option 3: Deploying Live to Render.com (Cloud Hosting)

This project is pre-configured with `render.yaml` and `Procfile` for instant free deployment on [Render](https://render.com):

1. Go to [Render Dashboard](https://dashboard.render.com/) and click **New + > Web Service**.
2. Connect your GitHub repository: `https://github.com/Bethalamanohar09/FTP-client-Server-Application`.
3. Set the following settings:
   - **Name**: `ftp-client-server-app`
   - **Environment**: `Python`
   - **Build Command**: *(leave empty)*
   - **Start Command**: `python app.py`
4. Click **Create Web Service**. Render will automatically detect the port and publish your website with a free HTTPS URL!

---

## 🔑 Pre-Configured Accounts

| Username | Password | Access Level | Description |
| :--- | :--- | :--- | :--- |
| `anonymous` | *(leave empty)* | Public / Guest | Standard public guest access |
| `admin` | `admin123` | Administrator | Full administrative privileges |
| `student` | `netlab` | Student | Standard laboratory account |

---

## 📂 Project Directory Structure

```
CN LAB PROJECT/
├── app.py                      # Web Application & FTP Server Engine (Single-command launcher)
├── server.py                   # Standalone multithreaded socket FTP server
├── client.py                   # Standalone interactive CLI socket FTP client
├── README.md                   # Complete lab documentation and viva-voce guide
├── storage/
│   ├── server/                 # Remote FTP server root directory
│   │   ├── welcome_server.txt
│   │   └── network_notes.md
│   └── client/                 # Local client storage root directory
│       ├── lab_report.txt
│       └── network_config.json
└── static/
    ├── index.html              # Modern glassmorphism UI & visualizer
    ├── css/
    │   └── style.css           # Styling, animations, packet particles
    └── js/
        └── app.js              # Client state machine, REST sync, packet animator
```

---

## 📡 RFC 959 Protocol Reference

### Supported Commands
- `USER <username>`: Identify user for authentication
- `PASS <password>`: Send password for authentication
- `PWD`: Print current working directory on server
- `CWD <dir>`: Change remote working directory
- `CDUP`: Change to parent directory
- `LIST`: Retrieve directory listing (over Data Connection)
- `RETR <file>`: Download file from server to client (Retrieve)
- `STOR <file>`: Upload file from client to server (Store)
- `DELE <file>`: Delete file on server
- `MKD <dir>`: Create new directory on server
- `TYPE <I/A>`: Set transfer representation mode (`I` = Binary/Image, `A` = ASCII)
- `PASV`: Enter Passive mode (Server opens ephemeral port)
- `PORT <h1,h2,h3,h4,p1,p2>`: Enter Active mode (Client opens port)
- `SIZE <file>`: Return file size in bytes
- `HELP`: Display list of recognized commands
- `QUIT`: Terminate control connection and close session

### Three-Digit Reply Codes Breakdown
- **1xx (Positive Preliminary)**: Action started (e.g., `150 Opening BINARY mode data connection`)
- **2xx (Positive Completion)**: Action completed successfully (e.g., `200 OK`, `220 Ready`, `226 Transfer complete`, `230 User logged in`)
- **3xx (Positive Intermediate)**: Command accepted, further information required (e.g., `331 Password required`)
- **4xx (Transient Negative)**: Temporary failure, try again (e.g., `425 Can't open data connection`)
- **5xx (Permanent Negative)**: Command rejected or fatal error (e.g., `530 Not logged in`, `550 File not found`)

---

## 🎓 Lab Viva-Voce Questions & Answers

### Q1: Why does FTP use two separate TCP connections?
> **Answer**: FTP separates **Control** (Port 21) from **Data** (Port 20 or dynamic ephemeral port). Control remains persistent throughout the session to send commands and receive status codes. The data connection is created dynamically only when data (file or directory listing) is transferred and closed immediately upon completion. This "out-of-band" architecture prevents control commands from being queued behind large file transfers.

### Q2: What is the difference between Active (PORT) and Passive (PASV) mode?
> **Answer**: 
> - **Active Mode**: The client informs the server of its IP and port using the `PORT` command. The **server** then initiates the data connection back to the client. This frequently fails in client networks behind NATs or firewalls.
> - **Passive Mode**: The client sends `PASV`. The **server** opens a random unprivileged port and returns its IP and port to the client. The **client** initiates the data connection, which smoothly traverses client firewalls.

### Q3: What is the difference between ASCII and Binary (Image) modes?
> **Answer**: ASCII mode translates line terminators between operating systems (e.g., `\r\n` on Windows vs `\n` on Unix/Linux). Binary (Image) mode transfers the byte stream verbatim without modification, which is required for images, executables, and compressed archives.
