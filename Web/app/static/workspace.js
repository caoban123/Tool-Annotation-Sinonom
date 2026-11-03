// Workspace Application Logic
const projectId = document.getElementById('app').dataset.projectId;

let hanSegments = [];
let vietSegments = [];
let alignments = [];

let selectedHan = new Set();
let selectedViet = new Set();
let currentFilter = 'all';
let searchQuery = '';

// Load initial data
document.addEventListener('DOMContentLoaded', () => {
  loadWorkspaceData();
  setupKeyboardShortcuts();
  setupSearch();
});

async function loadWorkspaceData() {
  try {
    showSaveStatus('Đang tải...', 'amber');
    const [segRes, alignRes] = await Promise.all([
      fetch(`/api/segments?project_id=${projectId}`),
      fetch(`/api/alignments?project_id=${projectId}`)
    ]);

    if (!segRes.ok || !alignRes.ok) throw new Error('Không thể tải dữ liệu workspace');

    const allSegs = await segRes.json();
    alignments = await alignRes.json();

    hanSegments = allSegs.filter(s => s.language === 'han');
    vietSegments = allSegs.filter(s => s.language === 'viet');

    document.getElementById('hanCount').innerText = `(${hanSegments.length})`;
    document.getElementById('vietCount').innerText = `(${vietSegments.length})`;

    renderColumns();
    updateSelectionPreview();
    showSaveStatus('Đã lưu DB', 'emerald');
  } catch (err) {
    showSaveStatus('Lỗi tải', 'rose');
    console.error(err);
  }
}

function showSaveStatus(text, color) {
  const el = document.getElementById('saveStatus');
  if (!el) return;
  const colors = {
    emerald: 'text-emerald-700 bg-emerald-500',
    amber: 'text-amber-700 bg-amber-500',
    rose: 'text-rose-700 bg-rose-500'
  };
  const parts = (colors[color] || colors.emerald).split(' ');
  el.className = `text-[11px] font-medium flex items-center space-x-1 pl-1 ${parts[0]}`;
  el.innerHTML = `<span class="w-2 h-2 rounded-full ${parts[1]} inline-block"></span><span>${text}</span>`;
}

function setFilter(filter) {
  currentFilter = filter;
  document.querySelectorAll('.filter-btn').forEach(b => {
    b.classList.remove('bg-white', 'text-slate-800', 'shadow-xs');
    b.classList.add('text-slate-600');
  });
  const activeBtn = document.getElementById(`filter-${filter}`);
  if (activeBtn) {
    activeBtn.classList.add('bg-white', 'text-slate-800', 'shadow-xs');
    activeBtn.classList.remove('text-slate-600');
  }
  renderColumns();
}

function setupSearch() {
  const input = document.getElementById('searchInput');
  if (input) {
    input.addEventListener('input', (e) => {
      searchQuery = e.target.value.toLowerCase().trim();
      renderColumns();
    });
  }
}

function renderColumns() {
  renderSide('han', hanSegments, document.getElementById('hanColumn'), selectedHan);
  renderSide('viet', vietSegments, document.getElementById('vietColumn'), selectedViet);
}

function renderSide(side, segments, container, selectedSet) {
  container.innerHTML = '';

  const filtered = segments.filter(seg => {
    // Filter by alignment status
    if (currentFilter !== 'all') {
      if (seg.alignment_status !== currentFilter) return false;
    }
    // Filter by search query
    if (searchQuery) {
      const matchText = seg.clean_text.toLowerCase().includes(searchQuery);
      const matchId = seg.id.toLowerCase().includes(searchQuery);
      if (!matchText && !matchId) return false;
    }
    return true;
  });

  if (filtered.length === 0) {
    container.innerHTML = `<div class="text-center py-10 text-slate-400 text-xs italic">Không có phân đoạn nào phù hợp.</div>`;
    return;
  }

  filtered.forEach(seg => {
    const isSelected = selectedSet.has(seg.id);
    const card = document.createElement('div');

    const statusBadge = getStatusBadge(seg.alignment_status);

    let borderClass = 'border-slate-200 hover:border-slate-300 bg-white';
    if (isSelected) {
      borderClass = side === 'han' 
        ? 'border-blue-500 bg-blue-50/70 ring-1 ring-blue-500 shadow-sm'
        : 'border-rose-500 bg-rose-50/70 ring-1 ring-rose-500 shadow-sm';
    } else if (seg.alignment_status === 'confirmed') {
      borderClass = 'border-emerald-200 bg-emerald-50/20';
    } else if (seg.alignment_status === 'needs_review') {
      borderClass = 'border-amber-300 bg-amber-50/30';
    } else if (seg.alignment_status === 'suggested') {
      borderClass = 'border-purple-200 bg-purple-50/20';
    }

    card.className = `p-3 rounded-lg border text-xs cursor-pointer transition select-none ${borderClass}`;
    card.id = `card_${seg.id}`;

    // Click handler for multi-select
    card.onclick = (e) => {
      // Ignore if clicking action buttons
      if (e.target.closest('button')) return;
      handleSegmentClick(side, seg, e.shiftKey);
    };

    card.innerHTML = `
      <div class="flex items-center justify-between pb-1.5 border-b border-slate-100">
        <div class="flex items-center space-x-1.5">
          <span class="font-mono text-[10px] text-slate-400 font-semibold">#${seg.order_index}</span>
          <span class="font-mono text-[10px] text-slate-500">${seg.id.split('_').slice(-2).join('_')}</span>
        </div>
        <div class="flex items-center space-x-1">
          ${statusBadge}
        </div>
      </div>
      <div class="mt-2 text-sm leading-relaxed text-slate-800 ${side === 'han' ? 'font-cjk font-normal text-base' : 'font-sans'}">
        ${escapeHtml(seg.clean_text)}
      </div>
      <div class="mt-2 pt-1.5 flex items-center justify-between text-[11px] text-slate-400">
        <span>Trang ${seg.page_ref}</span>
        <div class="flex items-center space-x-1.5">
          <button onclick="openEditModal('${seg.id}')" title="Sửa phân đoạn" class="hover:text-slate-700 px-1 py-0.5 rounded hover:bg-slate-100">Sửa</button>
          <button onclick="openSplitModal('${seg.id}')" title="Tách phân đoạn" class="hover:text-slate-700 px-1 py-0.5 rounded hover:bg-slate-100">Tách</button>
          <button onclick="deleteSegment('${seg.id}')" title="Xóa ô / phân đoạn này" class="text-slate-400 hover:text-rose-600 hover:bg-rose-50 px-1 py-0.5 rounded transition">Xóa ô</button>
          ${seg.alignment_id ? `
            <button onclick="deleteAlignment('${seg.alignment_id}')" title="Hủy xác nhận dóng hàng" class="text-rose-600 hover:text-white hover:bg-rose-600 bg-rose-50 border border-rose-200 px-1.5 py-0.5 rounded font-medium transition">Hủy dóng</button>
          ` : ''}
        </div>
      </div>
    `;

    container.appendChild(card);
  });
}

function getStatusBadge(status) {
  if (status === 'confirmed') {
    return `<span class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800">Đã dóng</span>`;
  } else if (status === 'needs_review') {
    return `<span class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-800">Cần duyệt</span>`;
  } else if (status === 'suggested') {
    return `<span class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-purple-100 text-purple-800">Gợi ý AI</span>`;
  }
  return `<span class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-500">Chưa gán</span>`;
}

function handleSegmentClick(side, segment, isShift) {
  const selectedSet = side === 'han' ? selectedHan : selectedViet;
  const segmentsList = side === 'han' ? hanSegments : vietSegments;

  if (isShift && selectedSet.size > 0) {
    // Select range
    const selectedIndices = Array.from(selectedSet).map(id => segmentsList.find(s => s.id === id).order_index);
    const minIdx = Math.min(...selectedIndices);
    const maxIdx = Math.max(...selectedIndices);
    const targetIdx = segment.order_index;

    const rangeStart = Math.min(minIdx, targetIdx);
    const rangeEnd = Math.max(maxIdx, targetIdx);

    for (let i = rangeStart; i <= rangeEnd; i++) {
      const s = segmentsList.find(seg => seg.order_index === i);
      if (s) selectedSet.add(s.id);
    }
  } else {
    // Toggle
    if (selectedSet.has(segment.id)) {
      selectedSet.delete(segment.id);
    } else {
      selectedSet.add(segment.id);
    }
  }

  renderColumns();
  updateSelectionPreview();
}

function updateSelectionPreview() {
  const hanSelectedSegs = hanSegments.filter(s => selectedHan.has(s.id)).sort((a,b) => a.order_index - b.order_index);
  const vietSelectedSegs = vietSegments.filter(s => selectedViet.has(s.id)).sort((a,b) => a.order_index - b.order_index);

  const numHan = hanSelectedSegs.length;
  const numViet = vietSelectedSegs.length;

  const badge = document.getElementById('cardinalityBadge');
  const preview = document.getElementById('previewText');
  const btn = document.getElementById('btnConfirm');

  if (numHan === 0 && numViet === 0) {
    const btnUnconfirm = document.getElementById('btnUnconfirm');
    if (btnUnconfirm) btnUnconfirm.style.display = 'none';
    badge.innerText = '0–0';
    badge.className = 'px-2 py-0.5 rounded font-mono font-bold bg-slate-200 text-slate-700';
    preview.innerHTML = '<em>Chọn phân đoạn Hán và Việt liền kề để dóng hàng...</em>';
    btn.disabled = true;
    return;
  }

  let type = '';
  if (numHan === 1 && numViet === 1) type = '1–1';
  else if (numHan === 1 && numViet >= 2) type = '1–n';
  else if (numHan >= 2 && numViet === 1) type = 'n–1';
  else if (numHan >= 2 && numViet >= 2) type = 'n–m';
  else type = `${numHan}–${numViet}`;

  // Validate contiguity
  let isHanContiguous = checkContiguity(hanSelectedSegs);
  let isVietContiguous = checkContiguity(vietSelectedSegs);

  let isValid = (numHan >= 1 && numViet >= 1 && isHanContiguous && isVietContiguous);

  badge.innerText = type;
  badge.className = isValid 
    ? 'px-2 py-0.5 rounded font-mono font-bold bg-emerald-100 text-emerald-800 border border-emerald-300'
    : 'px-2 py-0.5 rounded font-mono font-bold bg-amber-100 text-amber-800 border border-amber-300';

  let previewHtml = '';
  if (numHan > 0) {
    previewHtml += `<span class="font-cjk text-blue-900 font-medium">${hanSelectedSegs.map(s => escapeHtml(s.clean_text)).join(' ')}</span>`;
  }
  if (numHan > 0 && numViet > 0) {
    previewHtml += `<span class="mx-2 text-slate-400 font-bold">&harr;</span>`;
  }
  if (numViet > 0) {
    previewHtml += `<span class="font-sans text-rose-900">${vietSelectedSegs.map(s => escapeHtml(s.clean_text)).join(' ')}</span>`;
  }

  if (!isHanContiguous) {
    previewHtml += `<span class="text-amber-600 font-bold text-xs ml-2">(Hán không liền kề)</span>`;
  }
  if (!isVietContiguous) {
    previewHtml += `<span class="text-amber-600 font-bold text-xs ml-2">(Việt không liền kề)</span>`;
  }

  const btnUnconfirm = document.getElementById('btnUnconfirm');
  const selectedWithAlign = [...hanSelectedSegs, ...vietSelectedSegs].filter(s => s.alignment_id);
  if (selectedWithAlign.length > 0) {
    if (btnUnconfirm) {
      btnUnconfirm.style.display = 'inline-flex';
      const uniqueAlignCount = new Set(selectedWithAlign.map(s => s.alignment_id)).size;
      btnUnconfirm.innerHTML = `<svg class="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg><span>Hủy xác nhận (${uniqueAlignCount})</span>`;
    }
    previewHtml += `<span class="text-rose-600 font-semibold text-xs ml-2">(Có phân đoạn đã dóng - bấm Hủy xác nhận để gỡ)</span>`;
  } else {
    if (btnUnconfirm) {
      btnUnconfirm.style.display = 'none';
    }
  }

  preview.innerHTML = previewHtml;
  btn.disabled = (!isValid || selectedWithAlign.length > 0);
}

function checkContiguity(segs) {
  if (segs.length <= 1) return true;
  for (let i = 0; i < segs.length - 1; i++) {
    if (segs[i+1].order_index !== segs[i].order_index + 1) return false;
  }
  return true;
}

function clearSelection() {
  selectedHan.clear();
  selectedViet.clear();
  renderColumns();
  updateSelectionPreview();
}

async function confirmAlignment() {
  if (selectedHan.size === 0 || selectedViet.size === 0) return;
  const hanIds = Array.from(selectedHan);
  const vietIds = Array.from(selectedViet);

  try {
    showSaveStatus('Đang lưu...', 'amber');
    const res = await fetch('/api/alignments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: projectId,
        han_segment_ids: hanIds,
        viet_segment_ids: vietIds,
        status: 'confirmed'
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Lỗi khi tạo dóng hàng');
    }

    clearSelection();
    await loadWorkspaceData();
  } catch (err) {
    alert(err.message);
    showSaveStatus('Lỗi lưu', 'rose');
  }
}

async function undoAlignment() {
  try {
    showSaveStatus('Đang hoàn tác...', 'amber');
    const res = await fetch('/api/alignments/undo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Không thể hoàn tác');
    }
    await loadWorkspaceData();
  } catch (err) {
    alert(err.message);
    showSaveStatus('Đã lưu', 'emerald');
  }
}

async function deleteAlignment(alignId) {
  if (!confirm('Bạn có chắc muốn hủy xác nhận cặp dóng hàng này? Cặp phân đoạn sẽ chuyển lại trạng thái chưa gán.')) return;
  try {
    showSaveStatus('Đang hủy dóng...', 'amber');
    const res = await fetch(`/api/alignments/${alignId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Không thể hủy xác nhận cặp dóng hàng');
    await loadWorkspaceData();
    showSaveStatus('Đã hủy dóng', 'emerald');
  } catch (err) {
    alert(err.message);
    showSaveStatus('Lỗi hủy dóng', 'rose');
  }
}

async function unconfirmSelected() {
  const selected = [...hanSegments, ...vietSegments].filter(s => (selectedHan.has(s.id) || selectedViet.has(s.id)) && s.alignment_id);
  const alignIds = [...new Set(selected.map(s => s.alignment_id))];
  if (alignIds.length === 0) return;

  if (!confirm(`Bạn có chắc muốn hủy xác nhận ${alignIds.length} cặp dóng hàng đã chọn?`)) return;

  try {
    showSaveStatus('Đang hủy dóng...', 'amber');
    for (const id of alignIds) {
      const res = await fetch(`/api/alignments/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Không thể hủy xác nhận cặp dóng hàng');
    }
    clearSelection();
    await loadWorkspaceData();
    showSaveStatus('Đã hủy dóng', 'emerald');
  } catch (err) {
    alert(err.message);
    showSaveStatus('Lỗi hủy dóng', 'rose');
  }
}

async function deleteSegment(segId) {
  const seg = [...hanSegments, ...vietSegments].find(s => s.id === segId);
  if (!seg) return;

  const previewText = seg.clean_text.length > 40 ? seg.clean_text.substring(0, 40) + '...' : seg.clean_text;
  if (!confirm(`Bạn có chắc muốn xóa ô / phân đoạn này?\n\n"${previewText}"\n\nÔ này sẽ bị loại bỏ hoàn toàn và các ô sau sẽ tự động được đánh lại số thứ tự liên tục.`)) {
    return;
  }

  try {
    showSaveStatus('Đang xóa ô...', 'amber');
    const res = await fetch(`/api/segments/${segId}?project_id=${projectId}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Không thể xóa ô');
    }

    selectedHan.delete(segId);
    selectedViet.delete(segId);

    await loadWorkspaceData();
    showSaveStatus('Đã xóa ô', 'emerald');
  } catch (err) {
    alert('Lỗi xóa ô: ' + err.message);
    showSaveStatus('Lỗi xóa ô', 'rose');
  }
}

function setupKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    // If inside input or textarea, do not trigger global shortcuts
    if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
      return;
    }

    // Ctrl+Enter: Confirm
    if (e.ctrlKey && e.key === 'Enter') {
      e.preventDefault();
      confirmAlignment();
    }
    // Ctrl+Z: Undo
    else if (e.ctrlKey && e.key.toLowerCase() === 'z') {
      e.preventDefault();
      undoAlignment();
    }
    // Esc: Clear
    else if (e.key === 'Escape') {
      e.preventDefault();
      clearSelection();
    }
    // Ctrl+K: Focus search
    else if (e.ctrlKey && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      const s = document.getElementById('searchInput');
      if (s) { s.focus(); s.select(); }
    }
  });
}

// Edit Segment
function openEditModal(segId) {
  const seg = [...hanSegments, ...vietSegments].find(s => s.id === segId);
  if (!seg) return;
  document.getElementById('edit_seg_id').value = seg.id;
  document.getElementById('edit_seg_text').value = seg.clean_text;
  document.getElementById('editSegmentModal').classList.remove('hidden');
}

async function submitEditSegment() {
  const segId = document.getElementById('edit_seg_id').value;
  const newText = document.getElementById('edit_seg_text').value.trim();
  if (!newText) return;

  try {
    const res = await fetch(`/api/segments/${segId}?project_id=${projectId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clean_text: newText })
    });
    if (!res.ok) throw new Error(await res.text());
    document.getElementById('editSegmentModal').classList.add('hidden');
    await loadWorkspaceData();
  } catch (err) {
    alert('Lỗi: ' + err.message);
  }
}

// Split Segment
function openSplitModal(segId) {
  const seg = [...hanSegments, ...vietSegments].find(s => s.id === segId);
  if (!seg) return;
  document.getElementById('split_seg_id').value = seg.id;
  document.getElementById('split_seg_texts').value = seg.clean_text;
  document.getElementById('splitSegmentModal').classList.remove('hidden');
}

async function submitSplitSegment() {
  const segId = document.getElementById('split_seg_id').value;
  const raw = document.getElementById('split_seg_texts').value;
  const lines = raw.split('\n').map(l => l.trim()).filter(Boolean);

  if (lines.length < 2) {
    alert('Vui lòng nhập ít nhất 2 dòng để thực hiện tách phân đoạn.');
    return;
  }

  try {
    const res = await fetch(`/api/segments/split?project_id=${projectId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ segment_id: segId, split_texts: lines })
    });
    if (!res.ok) throw new Error(await res.text());
    document.getElementById('splitSegmentModal').classList.add('hidden');
    await loadWorkspaceData();
  } catch (err) {
    alert('Lỗi: ' + err.message);
  }
}

// Merge Segments
async function promptMergeSegments(side) {
  const selectedSet = side === 'han' ? selectedHan : selectedViet;
  if (selectedSet.size < 2) {
    alert(`Hãy chọn ít nhất 2 phân đoạn ${side === 'han' ? 'Hán' : 'Việt'} liền kề để gộp.`);
    return;
  }

  if (!confirm(`Bạn có chắc muốn gộp ${selectedSet.size} phân đoạn đã chọn thành một phân đoạn duy nhất?`)) return;

  try {
    const res = await fetch(`/api/segments/merge?project_id=${projectId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ segment_ids: Array.from(selectedSet) })
    });
    if (!res.ok) throw new Error(await res.text());
    clearSelection();
    await loadWorkspaceData();
  } catch (err) {
    alert('Lỗi: ' + err.message);
  }
}

// AI Suggestions Submit
async function submitAiSuggestions() {
  const fileInput = document.getElementById('ai_suggestions_file');
  if (!fileInput.files || fileInput.files.length === 0) {
    alert('Vui lòng chọn file suggestions.json');
    return;
  }

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);

  try {
    const res = await fetch(`/api/suggestions/import?project_id=${projectId}`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Lỗi nhập gợi ý');
    }
    const data = await res.json();
    alert(`Đã nhập thành công ${data.imported_suggestions_count} gợi ý từ model ${data.model_name}!`);
    document.getElementById('aiSuggestionsModal').classList.add('hidden');
    await loadWorkspaceData();
  } catch (err) {
    alert('Lỗi: ' + err.message);
  }
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.innerText = text;
  return div.innerHTML;
}
