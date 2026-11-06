// Han–Viet Alignment Studio — Workspace Application Logic
const projectId = document.getElementById('app').dataset.projectId;

let hanSegments = [];
let vietSegments = [];
let alignments = [];

let selectedHan = new Set();
let selectedViet = new Set();
let currentFilter = 'all';
let searchQuery = '';
let segmentById = new Map();
let segmentPosition = new Map();
let membershipBySegment = new Map();
let paintedSelection = new Set();
let mutationInFlight = false;
let workspaceLoadVersion = 0;
const PAGE_SIZE = 100;
const sidePage = {han: 0, viet: 0};
const qaTargetIds = new Set();

function rebuildWorkspaceIndex() {
  segmentById = new Map();
  segmentPosition = new Map();
  for (const segments of [hanSegments, vietSegments]) segments.forEach((seg, index) => {
    segmentById.set(seg.id, seg); segmentPosition.set(seg.id, index);
  });
  for (const selected of [selectedHan, selectedViet]) {
    for (const id of selected) if (!segmentById.has(id)) selected.delete(id);
  }
  membershipBySegment = new Map();
  for (const pair of alignments) indexPair(pair);
}

function indexPair(pair) {
  for (const seg of pair.han_segments.concat(pair.viet_segments)) {
    if (!membershipBySegment.has(seg.id)) membershipBySegment.set(seg.id, new Map());
    membershipBySegment.get(seg.id).set(pair.id, pair.status);
  }
}

function updateAlignmentProgress() {
  const el = document.getElementById('alignProgressText');
  if (el) el.innerText = `Đã xác nhận: ${alignments.filter(a => a.status === 'confirmed').length} cặp`;
}

function applyAlignmentDelta(pair, removedId = null) {
  const id = removedId || pair.id;
  const previous = alignments.find(a => a.id === id);
  if (removedId && !previous) return false;
  const affected = new Set();
  if (previous) for (const seg of previous.han_segments.concat(previous.viet_segments)) {
    affected.add(seg.id); membershipBySegment.get(seg.id)?.delete(id);
  }
  alignments = alignments.filter(a => a.id !== id);
  if (pair) {
    const compact = {id: pair.id, status: pair.status,
      han_segments: pair.han_segments.map(s => ({id: s.id})),
      viet_segments: pair.viet_segments.map(s => ({id: s.id}))};
    alignments.push(compact); indexPair(compact);
    for (const updated of pair.han_segments.concat(pair.viet_segments)) {
      affected.add(updated.id);
      // The mutation response includes the current text/revision of each member.
      const existing = segmentById.get(updated.id);
      if (existing) Object.assign(existing, updated);
    }
  }
  const priority = {confirmed: 4, needs_review: 3, suggested: 2, draft: 1};
  for (const segmentId of affected) {
    const seg = segmentById.get(segmentId);
    if (!seg) continue;
    seg.alignment_id = null; seg.alignment_status = 'unassigned';
    for (const [alignmentId, status] of membershipBySegment.get(segmentId) || []) {
      if ((priority[status] || 0) > (priority[seg.alignment_status] || 0)) {
        seg.alignment_id = alignmentId; seg.alignment_status = status;
      }
    }
  }
  if (currentFilter !== 'all' || searchQuery) renderColumns();
  else for (const segmentId of affected) {
    const seg = segmentById.get(segmentId), card = document.getElementById(`card_${segmentId}`);
    if (seg && card) card.replaceWith(createSegmentCard(seg.language, seg,
      seg.language === 'han' ? selectedHan : selectedViet));
  }
  refreshSelectionCards(); updateSelectionPreview(); updateAlignmentProgress();
  return true;
}

// Load initial data
document.addEventListener('DOMContentLoaded', () => {
  loadWorkspaceData();
  setupKeyboardShortcuts();
  setupSearch();
  setupWorkspaceOptions();
});

async function loadWorkspaceData() {
  const version = ++workspaceLoadVersion;
  try {
    showSaveStatus('Đang tải...', 'amber');
    const response = await fetch(`/api/workspace/${projectId}`);
    if (!response.ok) throw new Error('Không thể tải dữ liệu workspace');
    const snapshot = await response.json();
    if (version !== workspaceLoadVersion) return;
    const allSegs = snapshot.segments;
    alignments = snapshot.alignments;

    hanSegments = allSegs.filter(s => s.language === 'han');
    vietSegments = allSegs.filter(s => s.language === 'viet');
    rebuildWorkspaceIndex();

    const hanCountEl = document.getElementById('hanCount');
    const vietCountEl = document.getElementById('vietCount');
    if (hanCountEl) hanCountEl.innerText = `(${hanSegments.length})`;
    if (vietCountEl) vietCountEl.innerText = `(${vietSegments.length})`;

    updateAlignmentProgress();

    renderColumns();
    updateSelectionPreview();
    applyQaTarget();
    showSaveStatus('Đã lưu DB', 'emerald');
  } catch (err) {
    if (version !== workspaceLoadVersion) return;
    showSaveStatus('Lỗi tải', 'rose');
    console.error(err);
    if (window.showToast) window.showToast(err.message, 'error');
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
  el.className = `text-[11px] font-semibold flex items-center space-x-1 pl-1 ${parts[0]}`;
  el.innerHTML = `<span class="w-2 h-2 rounded-full ${parts[1]} inline-block"></span><span>${text}</span>`;
}

function setFilter(filter) {
  currentFilter = filter;
  sidePage.han = sidePage.viet = 0;
  document.querySelectorAll('.filter-btn').forEach(b => {
    b.classList.remove('bg-white', 'text-slate-900', 'shadow-xs', 'font-semibold');
    b.classList.add('text-slate-600');
  });
  const activeBtn = document.getElementById(`filter-${filter}`);
  if (activeBtn) {
    activeBtn.classList.add('bg-white', 'text-slate-900', 'shadow-xs', 'font-semibold');
    activeBtn.classList.remove('text-slate-600');
  }
  renderColumns();
}

function setupSearch() {
  const input = document.getElementById('searchInput');
  const clearBtn = document.getElementById('clearSearchBtn');
  let searchTimer;
  if (input) {
    input.addEventListener('input', (e) => {
      clearTimeout(searchTimer);
      searchQuery = e.target.value.toLowerCase().trim();
      if (clearBtn) {
        clearBtn.classList.toggle('hidden', searchQuery.length === 0);
      }
      sidePage.han = sidePage.viet = 0;
      searchTimer = setTimeout(renderColumns, 150);
    });
  }
}

function clearSearch() {
  const input = document.getElementById('searchInput');
  const clearBtn = document.getElementById('clearSearchBtn');
  if (input) input.value = '';
  if (clearBtn) clearBtn.classList.add('hidden');
  searchQuery = '';
  sidePage.han = sidePage.viet = 0;
  renderColumns();
}

function renderColumns() {
  const scrolls = ['hanColumn','vietColumn'].map(id=>document.getElementById(id).scrollTop);
  renderSide('han', hanSegments, document.getElementById('hanColumn'), selectedHan);
  renderSide('viet', vietSegments, document.getElementById('vietColumn'), selectedViet);
  paintedSelection = new Set([...selectedHan, ...selectedViet]);
  ['hanColumn','vietColumn'].forEach((id,index)=>document.getElementById(id).scrollTop=scrolls[index]);
  if(window.pendingCardFocus && !document.querySelector('[role=dialog]:not(.hidden)')){document.getElementById(window.pendingCardFocus)?.focus({preventScroll:true});window.pendingCardFocus=null;}

}

function segmentCardClasses(side, seg, isSelected) {
  let classes = 'rounded-xl border transition-all duration-150 cursor-pointer select-none relative group ';
  if (isSelected) {
    classes += side === 'han'
      ? 'border-sky-500 bg-sky-50/90 ring-2 ring-sky-400 shadow-md p-3.5'
      : 'border-rose-500 bg-rose-50/90 ring-2 ring-rose-400 shadow-md p-3.5';
  } else if (seg.alignment_status === 'confirmed') {
    classes += 'border-emerald-200 bg-emerald-50/30 hover:border-emerald-300 hover:shadow-xs p-3.5';
  } else if (seg.alignment_status === 'needs_review') {
    classes += 'border-amber-300 bg-amber-50/30 hover:border-amber-400 hover:shadow-xs p-3.5';
  } else if (seg.alignment_status === 'suggested') {
    classes += 'border-purple-200 bg-purple-50/30 hover:border-purple-300 hover:shadow-xs p-3.5';
  } else {
    classes += 'border-slate-200 hover:border-slate-300 bg-white hover:shadow-xs p-3.5';
  }
  return classes + ' segment-card';
}

function refreshSelectionCards() {
  const selected = new Set([...selectedHan, ...selectedViet]);
  for (const id of new Set([...paintedSelection, ...selected])) {
    const seg = segmentById.get(id), card = document.getElementById(`card_${id}`);
    if (!seg || !card) continue;
    const highlighted = card.classList.contains('qa-target');
    card.className = segmentCardClasses(seg.language, seg, selected.has(id));
    if (highlighted) card.classList.add('qa-target');
    card.dataset.selected = String(selected.has(id));
  }
  paintedSelection = selected;
}

function filteredSegments(side) {
  return (side === 'han' ? hanSegments : vietSegments).filter(seg => {
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
}

function renderPager(side, total) {
  const pager = document.getElementById(`${side}Pager`);
  if (!pager) return;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  sidePage[side] = Math.min(sidePage[side], pages - 1);
  pager.replaceChildren();
  const prev = document.createElement('button'); prev.textContent = 'Trước'; prev.disabled = sidePage[side] === 0;
  const next = document.createElement('button'); next.textContent = 'Sau'; next.disabled = sidePage[side] + 1 >= pages;
  prev.onclick = () => changeSidePage(side, -1); next.onclick = () => changeSidePage(side, 1);
  const label = document.createElement('span');
  label.textContent = total ? `${sidePage[side] * PAGE_SIZE + 1}–${Math.min(total, (sidePage[side] + 1) * PAGE_SIZE)} / ${total} ô` : '0 ô';
  const form = document.createElement('form');
  const input = document.createElement('input'); input.type = 'number'; input.min = '0'; input.placeholder = 'Số ô #';
  input.setAttribute('aria-label', `Đi tới số ô ${side === 'han' ? 'Hán' : 'Việt'}`);
  const go = document.createElement('button'); go.textContent = 'Đến'; go.type = 'submit';
  form.append(input, go);
  form.onsubmit = event => {
    event.preventDefault();
    if (input.value === '') return;
    const segment = (side === 'han' ? hanSegments : vietSegments).find(s => s.order_index === Number(input.value));
    if (segment) revealSegment(segment.id);
    else window.showToast?.('Không tìm thấy số ô này', 'warning');
  };
  pager.append(prev, label, next, form);
}

function changeSidePage(side, delta) {
  const count = filteredSegments(side).length;
  sidePage[side] = Math.max(0, Math.min(Math.max(0, Math.ceil(count / PAGE_SIZE) - 1), sidePage[side] + delta));
  renderSide(side, side === 'han' ? hanSegments : vietSegments,
    document.getElementById(`${side}Column`), side === 'han' ? selectedHan : selectedViet);
  document.getElementById(`${side}Column`).scrollTop = 0;
}

function revealSegment(id) {
  const seg = segmentById.get(id);
  if (!seg) return false;
  let filtered = filteredSegments(seg.language);
  if (!filtered.some(s => s.id === id)) {
    clearSearch(); setFilter('all');
    filtered = filteredSegments(seg.language);
  }
  sidePage[seg.language] = Math.floor(filtered.findIndex(s => s.id === id) / PAGE_SIZE);
  renderSide(seg.language, seg.language === 'han' ? hanSegments : vietSegments,
    document.getElementById(`${seg.language}Column`), seg.language === 'han' ? selectedHan : selectedViet);
  const card = document.getElementById(`card_${id}`);
  card?.scrollIntoView({block: 'center'}); card?.focus({preventScroll: true});
  return !!card;
}

function renderSide(side, segments, container, selectedSet) {
  if (!container) return;
  container.innerHTML = '';
  const filtered = filteredSegments(side);
  renderPager(side, filtered.length);

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="text-center py-16 px-4 bg-white/60 rounded-xl border border-dashed border-slate-300">
        <svg class="w-8 h-8 mx-auto text-slate-300 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
        <p class="text-slate-500 font-medium text-xs">Không có phân đoạn nào trong bộ lọc này.</p>
      </div>`;
    return;
  }

  const fragment = document.createDocumentFragment();
  filtered.slice(sidePage[side] * PAGE_SIZE, (sidePage[side] + 1) * PAGE_SIZE).forEach(seg => {
    fragment.appendChild(createSegmentCard(side, seg, selectedSet));
  });
  container.appendChild(fragment);
}

function createSegmentCard(side, seg, selectedSet) {
    const isSelected = selectedSet.has(seg.id);
    const card = document.createElement('div');

    const statusBadge = getStatusBadge(seg.alignment_status);

    card.className = segmentCardClasses(side, seg, isSelected);
    card.dataset.selected = String(isSelected);
    card.tabIndex = 0; card.setAttribute('role','group');
    card.setAttribute('aria-label', `${side === 'han' ? 'Hán' : 'Việt'} ${seg.order_index}, Enter để chọn, F2 để sửa`);
    card.title = 'Nhấp để chọn; nhấp đúp hoặc nhấn F2 để sửa nội dung';
    card.onkeydown = event => {
      if (event.target !== card) return;
      if (['Enter', ' '].includes(event.key)) {event.preventDefault();handleSegmentClick(side,seg,event.shiftKey);}
      else if (event.key === 'F2') {event.preventDefault();openEditModal(seg.id);}
    };
    card.id = `card_${seg.id}`;

    let selectionBeforeClick = null;
    const isCardAction = target => target.closest('button,a,input,textarea,select,[contenteditable="true"]');
    card.onclick = (e) => {
      if (isCardAction(e.target) || e.detail > 1) return;
      selectionBeforeClick = new Set(selectedSet);
      handleSegmentClick(side, seg, e.shiftKey);
    };
    card.ondblclick = (e) => {
      if (isCardAction(e.target)) return;
      e.preventDefault();
      e.stopPropagation();
      // The first click of a native double click already toggled selection.
      // Restore the prior set (including Shift ranges) before opening the editor.
      if (e.detail >= 2 && selectionBeforeClick) {
        selectedSet.clear();
        selectionBeforeClick.forEach(id => selectedSet.add(id));
        refreshSelectionCards();
        updateSelectionPreview();
      }
      card.focus({preventScroll:true});
      openEditModal(seg.id);
    };

    const isHan = (side === 'han');
    const indexBadgeClass = isHan
      ? 'bg-sky-100 text-sky-800 border-sky-200'
      : 'bg-rose-100 text-rose-800 border-rose-200';

    card.innerHTML = `
      <div class="flex flex-wrap gap-2 text-xs mb-2">
        <a class="source-ref" href="/source/${projectId}/${side}?page=${encodeURIComponent((seg.page_ref||'').split(',')[0])}#page=${encodeURIComponent((seg.page_ref||'').split(',')[0])}" target="_blank" rel="noopener">Mở nguồn</a>
        ${seg.alignment_status==='suggested'?`<button class="source-ref" onclick="reviewSuggestion('${seg.alignment_id}',true)">Duyệt gợi ý</button><button class="source-ref" onclick="reviewSuggestion('${seg.alignment_id}',false)">Từ chối</button>`:''}
        ${seg.alignment_status==='needs_review'?`<button class="source-ref" onclick="reconfirmPair('${seg.alignment_id}')">Xác nhận lại</button>`:''}
      </div>
      <!-- Top Card Header -->
      <div class="flex items-center justify-between pb-2 border-b border-slate-100/90">
        <div class="flex items-center space-x-2">
          <span class="font-mono text-[11px] font-bold px-2 py-0.5 rounded-md border ${indexBadgeClass}">#${seg.order_index}</span>
          <span class="font-mono text-[10px] text-slate-400 tracking-tight">${seg.id.split('_').slice(-2).join('_')}</span>
        </div>
        <div class="flex items-center space-x-1.5">
          ${seg.alignment_status === 'confirmed' ? `
            <span class="text-[10px] text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded font-mono font-semibold" title="Mã dóng: ${seg.alignment_id}">✓ Đã dóng</span>
          ` : statusBadge}
        </div>
      </div>

      <!-- Segment Text Body -->
      <div class="segment-text mt-2.5 ${isHan ? 'font-cjk text-[17px] leading-[1.8] text-slate-900 tracking-wide font-normal' : 'font-sans text-[14px] leading-relaxed text-slate-800 font-normal'}">
        ${escapeHtml(seg.clean_text)}
      </div>

      <!-- Card Action Footer -->
      <div class="mt-3 pt-2 flex items-center justify-between text-[11px] text-slate-400 border-t border-slate-100/70">
        <span class="font-medium text-[10px] text-slate-400">${seg.page_ref ? `Trang ${escapeHtml(seg.page_ref)}` : "Chưa rõ trang"}</span>
        
        <div class="flex items-center space-x-1">
          <button onclick="openEditModal('${seg.id}')" title="Sửa nội dung câu này"
            class="text-slate-600 hover:text-slate-900 hover:bg-slate-100 px-2 py-1 rounded-md transition font-medium flex items-center space-x-1">
            <svg class="w-3 h-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>
            <span>Sửa</span>
          </button>

          <button onclick="openSplitModal('${seg.id}')" title="Tách thành nhiều câu nhỏ"
            class="text-slate-600 hover:text-slate-900 hover:bg-slate-100 px-2 py-1 rounded-md transition font-medium flex items-center space-x-1">
            <svg class="w-3 h-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2"></path></svg>
            <span>Tách</span>
          </button>

          <button onclick="deleteSegment('${seg.id}')" title="Xóa bỏ ô này nếu là text rác / lỗi OCR"
            class="text-slate-400 hover:text-rose-600 hover:bg-rose-50 px-2 py-1 rounded-md transition font-medium flex items-center space-x-1">
            <svg class="w-3 h-3 text-slate-400 group-hover:text-rose-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
            <span>Xóa ô</span>
          </button>

          ${seg.alignment_id ? `
            <button onclick="deleteAlignment('${seg.alignment_id}')" title="Hủy xác nhận dóng hàng của ô này"
              class="text-rose-700 hover:text-white hover:bg-rose-600 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded-md font-bold text-[10px] transition flex items-center space-x-0.5">
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
              <span>Hủy dóng</span>
            </button>
          ` : ''}
        </div>
      </div>
    `;

    if (qaTargetIds.has(seg.id)) card.classList.add('qa-target');
    return card;
}

function getStatusBadge(status) {
  if (status === 'confirmed') {
    return `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">Đã dóng</span>`;
  } else if (status === 'needs_review') {
    return `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">Cần duyệt</span>`;
  } else if (status === 'suggested') {
    return `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-purple-100 text-purple-800 border border-purple-200">Gợi ý AI</span>`;
  }
  return `<span class="px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-100 text-slate-500 border border-slate-200">Chưa gán</span>`;
}

function handleSegmentClick(side, segment, isShift) {
  const selectedSet = side === 'han' ? selectedHan : selectedViet;
  const segmentsList = side === 'han' ? hanSegments : vietSegments;

  if (isShift && selectedSet.size > 0) {
    let rangeStart = segmentPosition.get(segment.id), rangeEnd = rangeStart;
    for (const id of selectedSet) {
      const index = segmentPosition.get(id);
      if (index !== undefined) {rangeStart = Math.min(rangeStart, index); rangeEnd = Math.max(rangeEnd, index);}
    }
    for (let i = rangeStart; i <= rangeEnd; i++) {
      const s = segmentsList[i];
      if (s) selectedSet.add(s.id);
    }
  } else {
    if (selectedSet.has(segment.id)) {
      selectedSet.delete(segment.id);
    } else {
      selectedSet.add(segment.id);
    }
  }

  refreshSelectionCards();
  updateSelectionPreview();
}

function updateSelectionPreview() {
  const hanSelectedSegs = [...selectedHan].map(id => segmentById.get(id)).filter(Boolean).sort((a,b) => a.order_index - b.order_index);
  const vietSelectedSegs = [...selectedViet].map(id => segmentById.get(id)).filter(Boolean).sort((a,b) => a.order_index - b.order_index);

  const numHan = hanSelectedSegs.length;
  const numViet = vietSelectedSegs.length;

  const badge = document.getElementById('cardinalityBadge');
  const preview = document.getElementById('previewText');
  const btn = document.getElementById('btnConfirm');
  const btnUnconfirm = document.getElementById('btnUnconfirm');

  if (numHan === 0 && numViet === 0) {
    if (btnUnconfirm) btnUnconfirm.style.display = 'none';
    if (badge) {
      badge.innerText = '0–0';
      badge.className = 'px-2.5 py-1 rounded-md font-mono font-bold text-xs bg-slate-200 text-slate-700';
    }
    if (preview) {
      preview.innerHTML = '<span class="italic text-slate-400">Chọn 1 hoặc nhiều phân đoạn Hán và Việt liền kề để dóng hàng...</span>';
    }
    if (btn) btn.disabled = true;
    return;
  }

  let type = '';
  if (numHan === 1 && numViet === 1) type = '1–1';
  else if (numHan === 1 && numViet >= 2) type = '1–n';
  else if (numHan >= 2 && numViet === 1) type = 'n–1';
  else if (numHan >= 2 && numViet >= 2) type = 'n–m';
  else type = `${numHan}–${numViet}`;

  const isHanContiguous = checkContiguity(hanSelectedSegs);
  const isVietContiguous = checkContiguity(vietSelectedSegs);
  const isValid = (numHan >= 1 && numViet >= 1 && isHanContiguous && isVietContiguous);

  if (badge) {
    badge.innerText = type;
    badge.className = isValid 
      ? 'px-2.5 py-1 rounded-md font-mono font-bold text-xs bg-emerald-100 text-emerald-800 border border-emerald-300 shadow-2xs'
      : 'px-2.5 py-1 rounded-md font-mono font-bold text-xs bg-amber-100 text-amber-800 border border-amber-300 shadow-2xs';
  }

  let previewHtml = '<div class="flex items-center space-x-2 text-xs">';
  if (numHan > 0) {
    previewHtml += `<div class="bg-sky-50 border border-sky-200 text-sky-900 px-2 py-1 rounded-md truncate max-w-xs font-cjk font-medium">${hanSelectedSegs.map(s => escapeHtml(s.clean_text)).join(' ')}</div>`;
  }
  if (numHan > 0 && numViet > 0) {
    previewHtml += `<span class="text-slate-400 font-bold">&harr;</span>`;
  }
  if (numViet > 0) {
    previewHtml += `<div class="bg-rose-50 border border-rose-200 text-rose-900 px-2 py-1 rounded-md truncate max-w-xs font-sans font-medium">${vietSelectedSegs.map(s => escapeHtml(s.clean_text)).join(' ')}</div>`;
  }

  if (!isHanContiguous) {
    previewHtml += `<span class="text-amber-600 font-bold text-xs ml-1">(Hán không liền kề)</span>`;
  }
  if (!isVietContiguous) {
    previewHtml += `<span class="text-amber-600 font-bold text-xs ml-1">(Việt không liền kề)</span>`;
  }
  previewHtml += '</div>';

  const selectedWithAlign = [...hanSelectedSegs, ...vietSelectedSegs].filter(s => s.alignment_id);
  if (selectedWithAlign.length > 0) {
    if (btnUnconfirm) {
      btnUnconfirm.style.display = 'inline-flex';
      const uniqueAlignCount = new Set(selectedWithAlign.map(s => s.alignment_id)).size;
      btnUnconfirm.innerHTML = `<svg class="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg><span>Hủy xác nhận (${uniqueAlignCount})</span>`;
    }
  } else {
    if (btnUnconfirm) btnUnconfirm.style.display = 'none';
  }

  if (preview) preview.innerHTML = previewHtml;
  if (btn) btn.disabled = (mutationInFlight || !isValid || selectedWithAlign.length > 0);
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
  refreshSelectionCards();
  updateSelectionPreview();
}

function jumpToNextUnassigned(side) {
  const segmentsList = (side === 'han') ? hanSegments : vietSegments;
  const unassigned = segmentsList.find(s => s.alignment_status === 'unassigned');
  if (!unassigned) {
    if (window.showToast) window.showToast(`Tất cả các ô ${side === 'han' ? 'Hán' : 'Việt'} đã được dóng hàng!`, 'info');
    return;
  }

  revealSegment(unassigned.id);
  const card = document.getElementById(`card_${unassigned.id}`);
  if (card) {
    card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    card.classList.add('ring-4', side === 'han' ? 'ring-sky-400' : 'ring-rose-400');
    setTimeout(() => {
      card.classList.remove('ring-4', side === 'han' ? 'ring-sky-400' : 'ring-rose-400');
    }, 1200);
  }
}

async function confirmAlignment() {
  if (mutationInFlight || selectedHan.size === 0 || selectedViet.size === 0) return;
  const hanIds = Array.from(selectedHan);
  const vietIds = Array.from(selectedViet);
  mutationInFlight = true;
  updateSelectionPreview();

  try {
    showSaveStatus('Đang lưu...', 'amber');
    const res = await fetch('/api/alignments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: projectId,
        task_id: document.getElementById('taskSelect').value || null,
        han_segment_ids: hanIds,
        viet_segment_ids: vietIds,
        status: 'confirmed'
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Lỗi khi tạo dóng hàng');
    }

    const data = await res.json();
    hanIds.forEach(id => selectedHan.delete(id));
    vietIds.forEach(id => selectedViet.delete(id));
    applyAlignmentDelta(data);
    showSaveStatus('Đã lưu DB', 'emerald');
    if (window.showToast) window.showToast(`Đã dóng cặp ${data.alignment_type} thành công!`, 'success');
  } catch (err) {
    if (window.showToast) window.showToast(err.message, 'error');
    else alert(err.message);
    showSaveStatus('Lỗi lưu', 'rose');
  } finally {
    mutationInFlight = false;
    updateSelectionPreview();
  }
}

async function undoAlignment() {
  if (mutationInFlight) return;
  mutationInFlight = true;
  updateSelectionPreview();
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
    const result = await res.json();
    if (!applyAlignmentDelta(null, result.undone_alignment_id)) await loadWorkspaceData();
    showSaveStatus('Đã lưu DB', 'emerald');
    if (window.showToast) window.showToast('Đã hoàn tác cặp dóng gần nhất', 'info');
  } catch (err) {
    if (window.showToast) window.showToast(err.message, 'error');
    else alert(err.message);
    showSaveStatus('Lỗi hoàn tác', 'rose');
  } finally {
    mutationInFlight = false;
    updateSelectionPreview();
  }
}

async function deleteAlignment(alignId) {
  if (!confirm('Bạn có chắc muốn hủy xác nhận cặp dóng hàng này? Cặp phân đoạn sẽ chuyển lại trạng thái chưa gán.')) return;
  try {
    showSaveStatus('Đang hủy dóng...', 'amber');
    const res = await fetch(`/api/alignments/${alignId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Không thể hủy xác nhận cặp dóng hàng');
    if (!applyAlignmentDelta(null, alignId)) await loadWorkspaceData();
    if (window.showToast) window.showToast('Đã hủy xác nhận dóng hàng', 'info');
    showSaveStatus('Đã hủy dóng', 'emerald');
  } catch (err) {
    if (window.showToast) window.showToast(err.message, 'error');
    else alert(err.message);
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
    if (window.showToast) window.showToast(`Đã hủy ${alignIds.length} cặp dóng hàng`, 'info');
    showSaveStatus('Đã hủy dóng', 'emerald');
  } catch (err) {
    if (window.showToast) window.showToast(err.message, 'error');
    else alert(err.message);
    showSaveStatus('Lỗi hủy dóng', 'rose');
  }
}

async function deleteSegment(segId) {
  const seg = segmentById.get(segId);
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
    if (window.showToast) window.showToast('Đã xóa ô phân đoạn và tự động đánh lại số thứ tự', 'info');
    showSaveStatus('Đã xóa ô', 'emerald');
  } catch (err) {
    if (window.showToast) window.showToast('Lỗi xóa ô: ' + err.message, 'error');
    else alert('Lỗi xóa ô: ' + err.message);
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
  const seg = segmentById.get(segId);
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
    if (window.showToast) window.showToast('Đã cập nhật nội dung phân đoạn', 'success');
  } catch (err) {
    if (window.showToast) window.showToast('Lỗi: ' + err.message, 'error');
    else alert('Lỗi: ' + err.message);
  }
}

// Split Segment
function openSplitModal(segId) {
  const seg = segmentById.get(segId);
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
    if (window.showToast) window.showToast('Vui lòng nhập ít nhất 2 dòng để tách', 'warning');
    else alert('Vui lòng nhập ít nhất 2 dòng để thực hiện tách phân đoạn.');
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
    if (window.showToast) window.showToast(`Đã tách thành ${lines.length} câu con`, 'success');
  } catch (err) {
    if (window.showToast) window.showToast('Lỗi: ' + err.message, 'error');
    else alert('Lỗi: ' + err.message);
  }
}

// Merge Segments
async function promptMergeSegments(side) {
  const selectedSet = side === 'han' ? selectedHan : selectedViet;
  if (selectedSet.size < 2) {
    if (window.showToast) window.showToast(`Hãy chọn ít nhất 2 ô ${side === 'han' ? 'Hán' : 'Việt'} liền kề để gộp`, 'warning');
    else alert(`Hãy chọn ít nhất 2 phân đoạn ${side === 'han' ? 'Hán' : 'Việt'} liền kề để gộp.`);
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
    if (window.showToast) window.showToast('Đã gộp các phân đoạn thành công', 'success');
  } catch (err) {
    if (window.showToast) window.showToast('Lỗi: ' + err.message, 'error');
    else alert('Lỗi: ' + err.message);
  }
}

// AI Suggestions Submit
async function submitAiSuggestions() {
  const fileInput = document.getElementById('ai_suggestions_file');
  if (!fileInput.files || fileInput.files.length === 0) {
    if (window.showToast) window.showToast('Vui lòng chọn file suggestions.json', 'warning');
    else alert('Vui lòng chọn file suggestions.json');
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
    document.getElementById('aiSuggestionsModal').classList.add('hidden');
    await loadWorkspaceData();
    if (window.showToast) window.showToast(`Đã nhập ${data.imported_suggestions_count} gợi ý; từ chối ${data.rejected_suggestions_count || 0}. ${data.rejected?.map(r=>`#${r.index+1}: ${r.reason}`).join("; ") || ""}`, 'success');
  } catch (err) {
    if (window.showToast) window.showToast('Lỗi: ' + err.message, 'error');
    else alert('Lỗi: ' + err.message);
  }
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.innerText = text;
  return div.innerHTML;
}

let qaTargetApplied=false;
function applyQaTarget(){
  if (qaTargetApplied) return;
  const query = new URLSearchParams(location.search), segment = query.get('segment'), alignmentId = query.get('alignment');
  if (!segment && !alignmentId) return;
  qaTargetApplied = true;
  const pair = alignments.find(a => a.id === alignmentId);
  const ids = segment ? [segment] : pair ? pair.han_segments.concat(pair.viet_segments).map(s => s.id) : [];
  const sides = new Set();
  for (const id of ids) {
    const seg = segmentById.get(id);
    if (!seg) continue;
    qaTargetIds.add(id);
    if (!sides.has(seg.language)) {
      const index = filteredSegments(seg.language).findIndex(s => s.id === id);
      sidePage[seg.language] = Math.max(0, Math.floor(index / PAGE_SIZE));
      sides.add(seg.language);
    }
  }
  renderColumns();
  for (const id of ids) {
    const card = document.getElementById(`card_${id}`);
    if (card) {card.scrollIntoView({block: 'center'}); card.focus({preventScroll: true});}
  }
  if (!sides.size) showToast('Không còn phân đoạn active tại vị trí này', 'warning');
}
async function reviewSuggestion(id,accept){try{await appRequest(`/api/suggestions/${id}/${accept?'accept':'reject'}`,{method:'POST'});await loadWorkspaceData();}catch(error){showToast(error.message,'error');}}
async function reconfirmPair(id){try{await appRequest(`/api/alignments/${id}/confirm`,{method:'POST'});await loadWorkspaceData();}catch(error){showToast(error.message,'error');}}
async function setupWorkspaceOptions(){
  const compact=document.getElementById('compactView'),size=document.getElementById('readingSize');
  try{compact.checked=localStorage.getItem('compactView')==='true';size.value=localStorage.getItem('readingSize')||16;}catch{}
  function apply(){document.getElementById('app').classList.toggle('compact',compact.checked);document.documentElement.style.setProperty('--reading-size',size.value+'px');try{localStorage.setItem('compactView',compact.checked);localStorage.setItem('readingSize',size.value);}catch{}}
  compact.onchange=apply;size.oninput=apply;apply();
  try{const tasks=await appRequest(`/api/projects/${projectId}/tasks`);const select=document.getElementById('taskSelect');for(const task of tasks){const option=document.createElement('option');option.value=task.id;option.textContent=task.assigned_to+' · '+task.scope;select.append(option);}}catch(error){showToast(error.message,'error');}
}
