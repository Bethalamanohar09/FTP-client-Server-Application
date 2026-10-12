/**
 * FTP Client-Server Application & Interactive Lab Workbench
 * Computer Networks Lab Project (RFC 959)
 */

document.addEventListener('DOMContentLoaded', () => {
  // ================= State =================
  const state = {
    isConnected: false,
    authenticated: false,
    user: null,
    mode: 'PASV',
    serverCwd: '/',
    clientCwd: '/',
    selectedClientFile: null,
    selectedServerFile: null,
    cmdHistory: [],
    historyIdx: -1,
    knownPacketIds: new Set()
  };

  // ================= DOM Elements =================
  const connStatusPill = document.getElementById('connStatusPill');
  const connStatusText = document.getElementById('connStatusText');
  const currentUserVal = document.getElementById('currentUserVal');
  const currentModeVal = document.getElementById('currentModeVal');
  const bytesUpVal = document.getElementById('bytesUpVal');
  const bytesDownVal = document.getElementById('bytesDownVal');
  
  const btnConnectModal = document.getElementById('btnConnectModal');
  const btnDisconnect = document.getElementById('btnDisconnect');
  const btnResetDemo = document.getElementById('btnResetDemo');
  const btnStudyGuide = document.getElementById('btnStudyGuide');

  // Network Vis
  const controlPacket = document.getElementById('controlPacket');
  const dataPacket = document.getElementById('dataPacket');

  // File Lists
  const clientFileListBody = document.getElementById('clientFileListBody');
  const serverFileListBody = document.getElementById('serverFileListBody');
  const clientPathVal = document.getElementById('clientPathVal');
  const serverPathVal = document.getElementById('serverPathVal');
  const serverAuthBadge = document.getElementById('serverAuthBadge');

  // File Actions
  const btnClientUp = document.getElementById('btnClientUp');
  const btnServerUp = document.getElementById('btnServerUp');
  const btnRefreshClient = document.getElementById('btnRefreshClient');
  const btnRefreshServer = document.getElementById('btnRefreshServer');
  const btnNewFolderClient = document.getElementById('btnNewFolderClient');
  const btnNewFolderServer = document.getElementById('btnNewFolderServer');
  const clientFileInput = document.getElementById('clientFileInput');
  const clientDropZone = document.getElementById('clientDropZone');

  // Bridge Transfer
  const btnTransferStor = document.getElementById('btnTransferStor');
  const btnTransferRetr = document.getElementById('btnTransferRetr');

  // Console & Sniffer
  const terminalScreen = document.getElementById('terminalScreen');
  const terminalInput = document.getElementById('terminalInput');
  const btnSendCmd = document.getElementById('btnSendCmd');
  const snifferTableBody = document.getElementById('snifferTableBody');
  const btnClearLog = document.getElementById('btnClearLog');

  // Modals
  const connectModal = document.getElementById('connectModal');
  const btnCloseConnectModal = document.getElementById('btnCloseConnectModal');
  const btnCancelConnect = document.getElementById('btnCancelConnect');
  const btnSubmitConnect = document.getElementById('btnSubmitConnect');
  const modalUsername = document.getElementById('modalUsername');
  const modalPassword = document.getElementById('modalPassword');
  const modalMode = document.getElementById('modalMode');
  const presetCards = document.querySelectorAll('.preset-card');

  const previewModal = document.getElementById('previewModal');
  const btnClosePreviewModal = document.getElementById('btnClosePreviewModal');
  const btnClosePreviewBtn = document.getElementById('btnClosePreviewBtn');
  const previewModalTitle = document.getElementById('previewModalTitle');
  const previewModalMeta = document.getElementById('previewModalMeta');
  const previewModalBody = document.getElementById('previewModalBody');

  const studyGuideModal = document.getElementById('studyGuideModal');
  const btnCloseStudyModal = document.getElementById('btnCloseStudyModal');
  const btnCloseStudyBtn = document.getElementById('btnCloseStudyBtn');

  // Toast Container
  const toastContainer = document.getElementById('toastContainer');

  // ================= Helpers =================
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icon = type === 'success' ? 'fa-circle-check' : (type === 'error' ? 'fa-circle-exclamation' : 'fa-circle-info');
    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${escapeHtml(message)}</span>`;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, m => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[m]);
  }

  function triggerPacketAnimation(channel, direction = 'c2s') {
    const el = channel === 'CONTROL' ? controlPacket : dataPacket;
    const animClass = direction === 'c2s' ? 'animating-c2s' : 'animating-s2c';
    el.classList.remove('animating-c2s', 'animating-s2c');
    void el.offsetWidth; // Force reflow
    el.classList.add(animClass);
  }

  function getFileIcon(name, isDir) {
    if (isDir) return '<i class="fa-solid fa-folder icon-folder file-icon"></i>';
    const ext = name.split('.').pop().toLowerCase();
    if (['txt', 'md', 'doc', 'pdf', 'csv'].includes(ext)) {
      return '<i class="fa-solid fa-file-lines icon-text file-icon"></i>';
    }
    if (['py', 'js', 'html', 'css', 'json', 'c', 'cpp', 'java'].includes(ext)) {
      return '<i class="fa-solid fa-file-code icon-code file-icon"></i>';
    }
    if (['png', 'jpg', 'jpeg', 'gif', 'svg'].includes(ext)) {
      return '<i class="fa-solid fa-file-image icon-image file-icon"></i>';
    }
    return '<i class="fa-solid fa-file icon-default file-icon"></i>';
  }

  // ================= API Calls =================
  async function fetchStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      updateStatusUI(data);
    } catch (e) {
      console.error('Error fetching status:', e);
    }
  }

  async function fetchFiles() {
    try {
      const res = await fetch('/api/files');
      const data = await res.json();
      renderClientFiles(data.client.files);
      renderServerFiles(data.server.files);
      clientPathVal.textContent = data.client.cwd;
      serverPathVal.textContent = data.server.cwd;
      state.clientCwd = data.client.cwd;
      state.serverCwd = data.server.cwd;
    } catch (e) {
      console.error('Error fetching files:', e);
    }
  }

  function updateStatusUI(data) {
    state.isConnected = data.is_connected;
    state.authenticated = data.authenticated;
    state.user = data.user;
    state.mode = data.mode;

    // Header Pills
    if (data.authenticated) {
      connStatusPill.innerHTML = '<span class="status-dot connected"></span><span class="status-text">CONNECTED</span>';
      currentUserVal.textContent = data.user;
      btnConnectModal.classList.add('hidden');
      btnDisconnect.classList.remove('hidden');
      serverAuthBadge.textContent = `Authenticated (${data.user})`;
      serverAuthBadge.className = 'badge badge-subtle';
    } else {
      connStatusPill.innerHTML = '<span class="status-dot disconnected"></span><span class="status-text">DISCONNECTED</span>';
      currentUserVal.textContent = 'None';
      btnConnectModal.classList.remove('hidden');
      btnDisconnect.classList.add('hidden');
      serverAuthBadge.textContent = 'Protected (Login Required)';
      serverAuthBadge.className = 'badge badge-purple';
    }

    currentModeVal.textContent = data.mode;
    bytesUpVal.textContent = data.bytes_uploaded_fmt;
    bytesDownVal.textContent = data.bytes_downloaded_fmt;

    // Process new packets for sniffer
    if (data.recent_packets) {
      data.recent_packets.forEach(packet => {
        if (!state.knownPacketIds.has(packet.id)) {
          state.knownPacketIds.add(packet.id);
          appendSnifferRow(packet);
        }
      });
    }
  }

  // ================= File Rendering =================
  function renderClientFiles(files) {
    clientFileListBody.innerHTML = '';
    if (!files || files.length === 0) {
      clientFileListBody.innerHTML = `<tr><td colspan="3" style="text-align:center; color: var(--text-muted); padding: 1.5rem;">Directory is empty</td></tr>`;
      return;
    }

    files.forEach(f => {
      const tr = document.createElement('tr');
      tr.className = 'file-row';
      if (state.selectedClientFile === f.name) tr.classList.add('selected');

      tr.innerHTML = `
        <td>
          <div class="file-name-cell">
            ${getFileIcon(f.name, f.is_dir)}
            <span>${escapeHtml(f.name)}</span>
          </div>
        </td>
        <td class="file-size-cell">${f.is_dir ? '<span class="badge badge-subtle">DIR</span>' : f.size_formatted}</td>
        <td>
          <div class="action-btns">
            ${!f.is_dir ? `<button class="row-action-btn" title="Upload to Server (STOR)" data-action="upload" data-name="${escapeHtml(f.name)}"><i class="fa-solid fa-arrow-right text-green"></i></button>` : ''}
            ${!f.is_dir ? `<button class="row-action-btn" title="Preview file" data-action="preview" data-name="${escapeHtml(f.name)}"><i class="fa-solid fa-eye"></i></button>` : ''}
            <button class="row-action-btn btn-del" title="Delete" data-action="delete" data-name="${escapeHtml(f.name)}"><i class="fa-solid fa-trash-can"></i></button>
          </div>
        </td>
      `;

      // Row Selection / Folder navigation
      tr.addEventListener('click', (e) => {
        if (e.target.closest('.row-action-btn')) return;
        if (f.is_dir) {
          navigateFolder('client', f.name);
        } else {
          document.querySelectorAll('.client-pane .file-row').forEach(r => r.classList.remove('selected'));
          tr.classList.add('selected');
          state.selectedClientFile = f.name;
        }
      });

      // Actions
      const uploadBtn = tr.querySelector('[data-action="upload"]');
      if (uploadBtn) {
        uploadBtn.addEventListener('click', () => transferFile('upload', f.name));
      }

      const previewBtn = tr.querySelector('[data-action="preview"]');
      if (previewBtn) {
        previewBtn.addEventListener('click', () => openPreview('client', f.name));
      }

      const delBtn = tr.querySelector('[data-action="delete"]');
      if (delBtn) {
        delBtn.addEventListener('click', () => deleteItem('client', f.name));
      }

      clientFileListBody.appendChild(tr);
    });
  }

  function renderServerFiles(files) {
    serverFileListBody.innerHTML = '';
    if (!files || files.length === 0) {
      serverFileListBody.innerHTML = `<tr><td colspan="3" style="text-align:center; color: var(--text-muted); padding: 1.5rem;">Directory is empty</td></tr>`;
      return;
    }

    files.forEach(f => {
      const tr = document.createElement('tr');
      tr.className = 'file-row';
      if (state.selectedServerFile === f.name) tr.classList.add('selected');

      tr.innerHTML = `
        <td>
          <div class="file-name-cell">
            ${getFileIcon(f.name, f.is_dir)}
            <span>${escapeHtml(f.name)}</span>
          </div>
        </td>
        <td class="file-size-cell">${f.is_dir ? '<span class="badge badge-subtle">DIR</span>' : f.size_formatted}</td>
        <td>
          <div class="action-btns">
            ${!f.is_dir ? `<button class="row-action-btn" title="Download to Client (RETR)" data-action="download" data-name="${escapeHtml(f.name)}"><i class="fa-solid fa-arrow-left text-cyan"></i></button>` : ''}
            ${!f.is_dir ? `<a class="row-action-btn" title="Save file to PC" href="/api/download_browser?target=server&filename=${encodeURIComponent(f.name)}" download><i class="fa-solid fa-download"></i></a>` : ''}
            ${!f.is_dir ? `<button class="row-action-btn" title="Preview file" data-action="preview" data-name="${escapeHtml(f.name)}"><i class="fa-solid fa-eye"></i></button>` : ''}
            <button class="row-action-btn btn-del" title="Delete (DELE)" data-action="delete" data-name="${escapeHtml(f.name)}"><i class="fa-solid fa-trash-can"></i></button>
          </div>
        </td>
      `;

      tr.addEventListener('click', (e) => {
        if (e.target.closest('.row-action-btn') || e.target.closest('a')) return;
        if (f.is_dir) {
          navigateFolder('server', f.name);
        } else {
          document.querySelectorAll('.server-pane .file-row').forEach(r => r.classList.remove('selected'));
          tr.classList.add('selected');
          state.selectedServerFile = f.name;
        }
      });

      const dlBtn = tr.querySelector('[data-action="download"]');
      if (dlBtn) {
        dlBtn.addEventListener('click', () => transferFile('download', f.name));
      }

      const previewBtn = tr.querySelector('[data-action="preview"]');
      if (previewBtn) {
        previewBtn.addEventListener('click', () => openPreview('server', f.name));
      }

      const delBtn = tr.querySelector('[data-action="delete"]');
      if (delBtn) {
        delBtn.addEventListener('click', () => deleteItem('server', f.name));
      }

      serverFileListBody.appendChild(tr);
    });
  }

  // ================= File Operations =================
  async function transferFile(direction, filename) {
    if (!state.authenticated) {
      showToast('Please login / connect to FTP server first!', 'error');
      openConnectModal();
      return;
    }

    triggerPacketAnimation('CONTROL', 'c2s');
    setTimeout(() => {
      triggerPacketAnimation('DATA', direction === 'upload' ? 'c2s' : 's2c');
    }, 200);

    try {
      const res = await fetch('/api/transfer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ direction, filename })
      });
      const data = await res.json();
      if (data.success) {
        showToast(data.message, 'success');
        appendTerminalLine(`S -> C: ${data.message}`, 'resp-2xx');
        fetchFiles();
        fetchStatus();
      } else {
        showToast(data.message || 'Transfer failed', 'error');
        appendTerminalLine(`S -> C: ${data.message}`, 'resp-5xx');
      }
    } catch (e) {
      showToast('Transfer request failed', 'error');
    }
  }

  async function navigateFolder(target, dir) {
    try {
      const res = await fetch('/api/navigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target, directory: dir })
      });
      const data = await res.json();
      if (data.success) {
        triggerPacketAnimation('CONTROL', 'c2s');
        fetchFiles();
        if (target === 'server') {
          appendTerminalLine(`C -> S: CWD ${dir}`, 'cmd');
          appendTerminalLine(`S -> C: 250 Directory changed to "${data.cwd}".`, 'resp-2xx');
        }
      } else {
        showToast(data.message || 'Navigation failed', 'error');
      }
    } catch (e) {
      console.error(e);
    }
  }

  async function deleteItem(target, filename) {
    const isConfirmed = confirm(`Are you sure you want to delete '${filename}' from ${target} storage?`);
    if (!isConfirmed) return;

    try {
      const res = await fetch('/api/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target, filename })
      });
      const data = await res.json();
      if (data.success) {
        showToast(data.message, 'success');
        triggerPacketAnimation('CONTROL', 'c2s');
        fetchFiles();
        if (target === 'server') {
          appendTerminalLine(`C -> S: DELE ${filename}`, 'cmd');
          appendTerminalLine(`S -> C: 250 ${data.message}`, 'resp-2xx');
        }
      } else {
        showToast(data.error || 'Delete failed', 'error');
      }
    } catch (e) {
      showToast('Error deleting item', 'error');
    }
  }

  async function createFolder(target) {
    const dirname = prompt(`Enter new folder name for ${target} storage:`);
    if (!dirname) return;

    try {
      const res = await fetch('/api/mkdir', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target, dirname })
      });
      const data = await res.json();
      if (data.success) {
        showToast(data.message, 'success');
        fetchFiles();
        if (target === 'server') {
          appendTerminalLine(`C -> S: MKD ${dirname}`, 'cmd');
          appendTerminalLine(`S -> C: 257 "${dirname}" directory created.`, 'resp-2xx');
        }
      } else {
        showToast(data.error || 'Could not create folder', 'error');
      }
    } catch (e) {
      showToast('Folder creation error', 'error');
    }
  }

  async function openPreview(target, filename) {
    try {
      const res = await fetch(`/api/preview?target=${target}&filename=${encodeURIComponent(filename)}`);
      const data = await res.json();
      if (data.error) {
        showToast(data.error, 'error');
        return;
      }

      previewModalTitle.textContent = `${filename} (${target.toUpperCase()} storage)`;
      previewModalMeta.textContent = `Size: ${data.size} bytes | Type: ${data.type}`;

      if (data.type === 'text') {
        previewModalBody.innerHTML = `<pre><code>${escapeHtml(data.content)}</code></pre>`;
      } else if (data.type === 'image') {
        previewModalBody.innerHTML = `<img src="${data.content}" alt="${escapeHtml(filename)}">`;
      } else {
        previewModalBody.innerHTML = `<p style="color: var(--text-muted); padding: 1rem;">${escapeHtml(data.content)}</p>`;
      }

      previewModal.classList.remove('hidden');
    } catch (e) {
      showToast('Could not load preview', 'error');
    }
  }

  // ================= Terminal & Command Engine =================
  function appendTerminalLine(text, typeClass = 'system-line') {
    const line = document.createElement('div');
    line.className = 'terminal-line';
    const timeStr = new Date().toTimeString().split(' ')[0];
    line.innerHTML = `
      <span class="line-time">[${timeStr}]</span>
      <span class="line-msg line-${typeClass}">${escapeHtml(text)}</span>
    `;
    terminalScreen.appendChild(line);
    terminalScreen.scrollTop = terminalScreen.scrollHeight;
  }

  async function sendFtpCommand(cmd) {
    cmd = cmd.trim();
    if (!cmd) return;

    state.cmdHistory.push(cmd);
    state.historyIdx = state.cmdHistory.length;

    appendTerminalLine(`C -> S: ${cmd}`, 'cmd');
    triggerPacketAnimation('CONTROL', 'c2s');

    try {
      const res = await fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmd })
      });
      const data = await res.json();
      
      let replyClass = 'resp-2xx';
      if (data.code >= 100 && data.code < 200) replyClass = 'resp-1xx';
      else if (data.code >= 300 && data.code < 400) replyClass = 'resp-3xx';
      else if (data.code >= 400 && data.code < 500) replyClass = 'resp-4xx';
      else if (data.code >= 500) replyClass = 'resp-5xx';

      appendTerminalLine(`S -> C: ${data.message}`, replyClass);
      triggerPacketAnimation('CONTROL', 's2c');

      // If LIST command, also show directory listing
      if (data.listing && Array.isArray(data.listing)) {
        data.listing.forEach(l => {
          appendTerminalLine(`  ${l}`, 'resp-1xx');
        });
      }

      fetchStatus();
      fetchFiles();
    } catch (e) {
      appendTerminalLine('Error connecting to FTP server engine', 'resp-5xx');
    }
  }

  // ================= Sniffer Table =================
  function appendSnifferRow(packet) {
    const tr = document.createElement('tr');
    const tagClass = packet.channel === 'CONTROL' ? 'tag-control' : 'tag-data';
    tr.innerHTML = `
      <td>${packet.timestamp}</td>
      <td><span class="${tagClass}">${packet.channel}</span></td>
      <td>${packet.port}</td>
      <td><strong>${escapeHtml(packet.direction)}</strong></td>
      <td style="color: #cbd5e1;">${escapeHtml(packet.message)}</td>
      <td style="color: var(--text-muted);">${escapeHtml(packet.note || '')}</td>
    `;
    snifferTableBody.insertBefore(tr, snifferTableBody.firstChild);

    // Keep max 50 rows in sniffer DOM
    while (snifferTableBody.children.length > 50) {
      snifferTableBody.removeChild(snifferTableBody.lastChild);
    }
  }

  // ================= Drag and Drop Upload to Client =================
  clientDropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    clientDropZone.style.border = '2px dashed var(--cyan)';
  });

  clientDropZone.addEventListener('dragleave', () => {
    clientDropZone.style.border = 'none';
  });

  clientDropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    clientDropZone.style.border = 'none';
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleClientFileUpload(e.dataTransfer.files[0]);
    }
  });

  clientFileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleClientFileUpload(e.target.files[0]);
    }
  });

  function handleClientFileUpload(file) {
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const res = await fetch('/api/upload_file', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target: 'client',
            filename: file.name,
            content: reader.result
          })
        });
        const data = await res.json();
        if (data.success) {
          showToast(`File '${file.name}' added to client storage`, 'success');
          fetchFiles();
        } else {
          showToast(data.error || 'Upload error', 'error');
        }
      } catch (err) {
        showToast('Failed to save file', 'error');
      }
    };
    reader.readAsDataURL(file);
  }

  // ================= Modal Actions =================
  function openConnectModal() {
    connectModal.classList.remove('hidden');
  }

  function closeConnectModal() {
    connectModal.classList.add('hidden');
  }

  presetCards.forEach(card => {
    card.addEventListener('click', () => {
      presetCards.forEach(c => c.classList.remove('active'));
      card.classList.add('active');
      modalUsername.value = card.dataset.user;
      modalPassword.value = card.dataset.pwd;
    });
  });

  btnSubmitConnect.addEventListener('click', async () => {
    const user = modalUsername.value.trim() || 'anonymous';
    const password = modalPassword.value.trim();
    const mode = modalMode.value;

    triggerPacketAnimation('CONTROL', 'c2s');
    try {
      const res = await fetch('/api/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user, password, mode })
      });
      const data = await res.json();
      if (data.success) {
        showToast(`Connected as ${user}!`, 'success');
        appendTerminalLine(`S -> C: ${data.message}`, 'resp-2xx');
        closeConnectModal();
        fetchStatus();
        fetchFiles();
      } else {
        showToast(data.message || 'Authentication failed', 'error');
        appendTerminalLine(`S -> C: ${data.message}`, 'resp-5xx');
      }
    } catch (e) {
      showToast('Connection failed', 'error');
    }
  });

  btnDisconnect.addEventListener('click', async () => {
    triggerPacketAnimation('CONTROL', 'c2s');
    try {
      const res = await fetch('/api/disconnect', { method: 'POST' });
      const data = await res.json();
      showToast('Disconnected from FTP Server', 'info');
      appendTerminalLine('S -> C: 221 Goodbye. Service closing control connection.', 'resp-2xx');
      fetchStatus();
      fetchFiles();
    } catch (e) {
      console.error(e);
    }
  });

  // ================= Event Listeners =================
  btnConnectModal.addEventListener('click', openConnectModal);
  btnCloseConnectModal.addEventListener('click', closeConnectModal);
  btnCancelConnect.addEventListener('click', closeConnectModal);

  btnClosePreviewModal.addEventListener('click', () => previewModal.classList.add('hidden'));
  btnClosePreviewBtn.addEventListener('click', () => previewModal.classList.add('hidden'));

  btnStudyGuide.addEventListener('click', () => studyGuideModal.classList.remove('hidden'));
  btnCloseStudyModal.addEventListener('click', () => studyGuideModal.classList.add('hidden'));
  btnCloseStudyBtn.addEventListener('click', () => studyGuideModal.classList.add('hidden'));

  btnTransferStor.addEventListener('click', () => {
    if (!state.selectedClientFile) {
      showToast('Click a file in the Local Client table first!', 'info');
      return;
    }
    transferFile('upload', state.selectedClientFile);
  });

  btnTransferRetr.addEventListener('click', () => {
    if (!state.selectedServerFile) {
      showToast('Click a file in the Remote Server table first!', 'info');
      return;
    }
    transferFile('download', state.selectedServerFile);
  });

  btnClientUp.addEventListener('click', () => navigateFolder('client', '..'));
  btnServerUp.addEventListener('click', () => navigateFolder('server', '..'));

  btnRefreshClient.addEventListener('click', fetchFiles);
  btnRefreshServer.addEventListener('click', () => {
    if (state.authenticated) {
      sendFtpCommand('LIST');
    } else {
      fetchFiles();
    }
  });

  btnNewFolderClient.addEventListener('click', () => createFolder('client'));
  btnNewFolderServer.addEventListener('click', () => {
    if (!state.authenticated) {
      showToast('Login required to create folders on server (MKD)', 'error');
      return;
    }
    createFolder('server');
  });

  btnResetDemo.addEventListener('click', async () => {
    const isConfirmed = confirm('Reset demo files on client and server to initial defaults?');
    if (!isConfirmed) return;
    try {
      const res = await fetch('/api/reset_demo', { method: 'POST' });
      const data = await res.json();
      showToast('Demo environment reset!', 'success');
      fetchFiles();
      fetchStatus();
    } catch (e) {
      showToast('Error resetting demo', 'error');
    }
  });

  // Tab switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.tab).classList.add('active');
    });
  });

  // Terminal Input & Quick Chips
  btnSendCmd.addEventListener('click', () => {
    sendFtpCommand(terminalInput.value);
    terminalInput.value = '';
  });

  terminalInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      sendFtpCommand(terminalInput.value);
      terminalInput.value = '';
    } else if (e.key === 'ArrowUp') {
      if (state.historyIdx > 0) {
        state.historyIdx--;
        terminalInput.value = state.cmdHistory[state.historyIdx];
      }
    } else if (e.key === 'ArrowDown') {
      if (state.historyIdx < state.cmdHistory.length - 1) {
        state.historyIdx++;
        terminalInput.value = state.cmdHistory[state.historyIdx];
      } else {
        state.historyIdx = state.cmdHistory.length;
        terminalInput.value = '';
      }
    }
  });

  document.querySelectorAll('.cmd-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      terminalInput.value = chip.dataset.cmd;
      terminalInput.focus();
    });
  });

  btnClearLog.addEventListener('click', () => {
    terminalScreen.innerHTML = '';
    snifferTableBody.innerHTML = '';
    showToast('Logs cleared', 'info');
  });

  // Initial Load & Heartbeat
  fetchFiles();
  fetchStatus();
  setInterval(fetchStatus, 2500);
});
