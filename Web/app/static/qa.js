const qaProject=document.getElementById('qaApp').dataset.projectId;
let sampleAlignments=[],sampleReviews=[],samplePage=0;
const qaEsc=text=>{const el=document.createElement('span');el.textContent=text??'';return el.innerHTML;};
async function refreshQa(){
  try{
    const [issues,stats]=await Promise.all([appRequest(`/api/qa?project_id=${qaProject}`),appRequest(`/api/projects/${qaProject}/stats`)]);
    document.getElementById('qaSummary').textContent=`Mẫu hợp lệ: ${stats.checked_sample_size} cặp · Cặp lỗi: ${stats.checked_error_count} · Tỷ lệ: ${stats.error_rate_pct===null?'Chưa đánh giá':stats.error_rate_pct+'%'} · Vấn đề đang mở: ${stats.qa_issues_count}`;
    const body=document.getElementById('issuesTableBody');body.replaceChildren();
    const selected=document.getElementById('issueStatus').value;
    for(const issue of issues.filter(i=>selected==='all'||i.status===selected)){
      const row=document.createElement('tr');row.className='border-b border-slate-200';
      const target=new URLSearchParams(issue.segment_id?{segment:issue.segment_id}:{alignment:issue.alignment_id||''});
      row.innerHTML=`<td class="p-3">${qaEsc(issue.code)}<br><small>${qaEsc(issue.origin)}</small></td><td class="p-3">${qaEsc(issue.comment)}</td><td class="p-3">${issue.alignment_id||issue.segment_id?`<a class="source-ref" href="/workspace/${qaProject}?${target}">Tới vị trí lỗi</a>`:'—'}</td><td class="p-3"></td>`;
      const button=document.createElement('button');button.className='action';button.textContent=issue.status==='open'?'Đã xử lý':issue.status;button.disabled=issue.status!=='open';
      button.onclick=async()=>{try{await appRequest(`/api/qa/${issue.id}/resolve`,{method:'POST'});await refreshQa();}catch(error){showToast(error.message,'error');}};
      row.lastElementChild.append(button);body.append(row);
    }
    if(!body.children.length){const row=body.insertRow();const cell=row.insertCell();cell.colSpan=4;cell.className='p-4';cell.textContent='Không có vấn đề trong bộ lọc. Quét tự động không xác nhận tính đúng ngữ nghĩa.';}
  }catch(error){showToast(error.message,'error');}
}
async function loadSample(){
  try{const [all,reviews]=await Promise.all([appRequest(`/api/alignments?project_id=${qaProject}`),appRequest(`/api/qa/reviews?project_id=${qaProject}`)]);sampleAlignments=all.filter(a=>a.status==='confirmed');sampleReviews=reviews;renderPending(all.filter(a=>['suggested','draft','needs_review'].includes(a.status)));renderSample();await refreshQa();}
  catch(error){showToast(error.message,'error');}
}
function renderPending(alignments){
  const root=document.getElementById('pendingPairs');root.replaceChildren();
  if(!alignments.length){root.textContent='Không còn cặp chờ duyệt.';return;}
  for(const alignment of alignments){
    const row=document.createElement('div');row.className='sample-row';
    const label=document.createElement('p');label.textContent=`${alignment.id} · ${alignment.status}`;row.append(label);
    const texts=document.createElement('div');texts.className='sample-pair';
    for(const segments of [alignment.han_segments,alignment.viet_segments]){const text=document.createElement('p');text.textContent=segments.map(s=>s.clean_text+(s.active?'':' [không còn active]')).join('\n');texts.append(text);}row.append(texts);
    const actions=document.createElement('div');actions.className='sample-actions';
    for(const [caption,path,method] of [
      ['Duyệt cặp',alignment.status==='suggested'?`/api/suggestions/${alignment.id}/accept`:`/api/alignments/${alignment.id}/confirm`,'POST'],
      [alignment.status==='suggested'?'Từ chối gợi ý':'Hủy cặp chờ duyệt',alignment.status==='suggested'?`/api/suggestions/${alignment.id}/reject`:`/api/alignments/${alignment.id}` ,alignment.status==='suggested'?'POST':'DELETE']]){
      const button=document.createElement('button');button.className='action';button.textContent=caption;
      button.onclick=async()=>{if(method==='DELETE'&&!confirm('Hủy cặp chờ duyệt này? Lịch sử thao tác vẫn được giữ.'))return;try{await appRequest(path,{method});await loadSample();}catch(error){showToast(error.message,'error');}};actions.append(button);
    }
    row.append(actions);root.append(row);
  }
}
function renderSample(){
  const search=document.getElementById('sampleSearch').value.toLowerCase();
  const filtered=sampleAlignments.filter(a=>JSON.stringify(a.han_segments.map(s=>s.clean_text).concat(a.viet_segments.map(s=>s.clean_text),a.id)).toLowerCase().includes(search));
  samplePage=Math.max(0,Math.min(samplePage,Math.ceil(filtered.length/20)-1));
  document.getElementById('samplePage').textContent=`Trang ${samplePage+1}/${Math.max(1,Math.ceil(filtered.length/20))} · ${filtered.length} cặp`;
  const root=document.getElementById('sampleRows');root.replaceChildren();
  for(const alignment of filtered.slice(samplePage*20,(samplePage+1)*20)){
    const review=sampleReviews.find(r=>r.alignment_id===alignment.id);
    const form=document.createElement('form');form.className='sample-row';
    form.innerHTML=`<div class="flex flex-wrap justify-between gap-2"><a class="source-ref" href="/workspace/${qaProject}?alignment=${encodeURIComponent(alignment.id)}">${qaEsc(alignment.id)} · ${qaEsc(alignment.alignment_type)}</a><span class="text-xs">${review?(review.current?'Đã kiểm tra: ':'Cần kiểm tra lại: ')+qaEsc(review.outcome):'Chưa kiểm tra'}</span></div>
      <div class="sample-pair mt-3"><div class="font-cjk">${qaEsc(alignment.han_segments.map(s=>s.clean_text).join('\n'))}</div><div>${qaEsc(alignment.viet_segments.map(s=>s.clean_text).join('\n'))}</div></div>
      <div class="sample-actions"><label>Kết luận <select name="outcome"><option value="correct">Đúng</option><option value="error">Có lỗi</option></select></label>
      ${['OMISSION','ADDITION','MISSING'].map(code=>`<label><input type="checkbox" name="error_codes" value="${code}"> ${code}</label>`).join('')}
      <label>Người kiểm tra <input name="reviewer" maxlength="128"></label><label>Ghi chú <input name="note"></label><button class="action">Lưu đánh giá</button></div>`;
    if(review){form.elements.outcome.value=review.outcome;form.elements.note.value=review.note;form.elements.reviewer.value=review.reviewer;form.querySelectorAll('[name=error_codes]').forEach(input=>input.checked=review.error_codes.includes(input.value));}
    form.onsubmit=async event=>{event.preventDefault();try{const data=new FormData(form);await appRequest(`/api/qa/reviews/${alignment.id}`,{method:'POST',body:JSON.stringify({outcome:data.get('outcome'),error_codes:data.getAll('error_codes'),note:data.get('note'),reviewer:data.get('reviewer')})});await loadSample();showToast('Đã lưu đánh giá mẫu','success');}catch(error){showToast(error.message,'error');}};
    root.append(form);
  }
  if(!filtered.length)root.textContent='Chưa có cặp xác nhận phù hợp để kiểm tra.';
}
document.getElementById('scanQa').onclick=async()=>{try{await appRequest(`/api/qa/scan?project_id=${qaProject}`,{method:'POST'});await refreshQa();showToast('Đã quét cảnh báo tự động; đánh giá thủ công được giữ nguyên','success');}catch(error){showToast(error.message,'error');}};
document.getElementById('issueStatus').onchange=refreshQa;
document.getElementById('sampleSearch').oninput=()=>{samplePage=0;renderSample();};
document.getElementById('samplePrev').onclick=()=>{samplePage--;renderSample();};
document.getElementById('sampleNext').onclick=()=>{samplePage++;renderSample();};
loadSample();
