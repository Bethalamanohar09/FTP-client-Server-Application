# Computer Networks Lab - File Transfer Protocol Notes

## FTP Architecture Overview
FTP uses two parallel TCP connections to transfer a file:
1. **Control Connection**: Remains open throughout the session. Used for commands like USER, PASS, CWD, RETR, STOR.
2. **Data Connection**: Opened on demand each time data (directory list or file) needs to be sent, and closed once transfer finishes.

## Important RFC 959 Commands:
- `USER <name>`: Identify user
- `PASS <pwd>`: Send password
- `LIST`: List files in current directory
- `RETR <file>`: Retrieve (download) file from server
- `STOR <file>`: Store (upload) file onto server
- `PWD`: Print working directory
- `CWD <path>`: Change working directory
- `QUIT`: Close control connection

## Response Code Structure:
- 1xx: Positive Preliminary Reply (action started)
- 2xx: Positive Completion Reply (action completed)
- 3xx: Positive Intermediate Reply (more info needed, e.g. password)
- 4xx: Transient Negative Reply (try again later)
- 5xx: Permanent Negative Reply (syntax error, permission denied)
