const sourceProject = document.getElementById('sourcesApp').dataset.projectId;
const sourceFields = {title:'Tên tài liệu',url:'URL nguồn',filename:'Tên tệp',format:'Định dạng (PDF/ảnh/TXT)',page_count:'Số trang tài liệu',scope:'Phạm vi quyển/chương/trang',tools:'Công cụ xử lý và phiên bản',notes:'Ghi chú nguồn'};
async function loadSourceForms() {
  try {
    const data = await appRequest(`/api/projects/${sourceProject}/sources`);
    const root = document.getElementById('sourceForms'); root.replaceChildren();
    for (const language of ['han','viet']) {
      const item = data[language]; const form = document.createElement('form'); form.className = 'panel'; form.id = language;
      const heading = document.createElement('h2'); heading.className = 'text-lg font-bold'; heading.textContent = language === 'han' ? 'Nguồn Hán' : 'Nguồn Việt'; form.append(heading);
      for (const [name,label] of Object.entries(sourceFields)) {
        const wrapper = document.createElement('label'); wrapper.className = 'field'; wrapper.textContent = label;
        const input = document.createElement('input'); input.name = name; input.type = name === 'page_count' ? 'number' : name === 'url' ? 'url' : 'text';
        if (name === 'page_count') input.min = '1'; input.value = item.source?.[name] ?? ''; wrapper.append(input); form.append(wrapper);
      }
      const save = document.createElement('button'); save.className = 'action'; save.textContent = 'Lưu kiểm kê'; form.append(save);
      form.onsubmit = async e => {e.preventDefault(); try {
        const payload = Object.fromEntries(new FormData(form)); payload.page_count = payload.page_count ? Number(payload.page_count) : null;
        await appRequest(`/api/projects/${sourceProject}/sources/${language}`, {method:'PUT',body:JSON.stringify(payload)}); showToast('Đã lưu thông tin nguồn','success');
      } catch(error) {showToast(error.message,'error');}};
      const upload = document.createElement('label'); upload.className = 'field'; upload.textContent = 'Tệp nguồn gốc để đóng gói (không bắt buộc)';
      const file = document.createElement('input'); file.type = 'file'; upload.append(file); form.append(upload);
      file.onchange = async () => {if (!file.files[0]) return; try {const body = new FormData(); body.append('file',file.files[0]); await appRequest(`/api/projects/${sourceProject}/sources/${language}/file`,{method:'POST',body}); showToast('Đã lưu tệp nguồn trong database','success');} catch(error){showToast(error.message,'error');}};
      const metadata = document.createElement('label'); metadata.className = 'field'; metadata.textContent = 'Metadata OCR JSON khớp TXT (gắn trước khi biên tập)';
      const metaFile = document.createElement('input'); metaFile.type = 'file'; metaFile.accept = '.json'; metadata.append(metaFile); form.append(metadata);
      metaFile.onchange = async () => {if(!metaFile.files[0]) return; try {const body = new FormData(); body.append('file',metaFile.files[0]); await appRequest(`/api/projects/${sourceProject}/metadata/${language}`,{method:'POST',body}); showToast('Đã gắn số trang nguồn','success');} catch(error){showToast(error.message,'error');}};
      const info = document.createElement('p'); info.className = 'text-xs mt-3 text-slate-500'; info.textContent = item.document_id ? `TXT: ${item.filename} · SHA256: ${item.raw_sha256}` : 'Chưa nhập TXT cho ngôn ngữ này'; form.append(info);
      if (!item.document_id) form.querySelectorAll('input,button').forEach(input=>input.disabled=true);
      root.append(form);
    }
    const tasks = await appRequest(`/api/projects/${sourceProject}/tasks`); document.getElementById('taskForms').replaceChildren();
    tasks.forEach(task=>taskForm(task));
  } catch(error) {showToast(error.message,'error');}
}
function taskForm(task={assigned_to:'',scope:'',target_count:2000}) {
  const form = document.createElement('form'); form.className = 'task-form';
  for (const [name,label] of Object.entries({assigned_to:'Người thực hiện',scope:'Phạm vi',target_count:'Mục tiêu cặp'})) {
    const field = document.createElement('label'); field.className='field'; field.textContent=label;
    const input=document.createElement('input'); input.name=name; input.required=true; input.type=name==='target_count'?'number':'text'; input.min='1'; input.value=task[name]; field.append(input); form.append(field);
  }
  const save=document.createElement('button'); save.className='action'; save.textContent='Lưu nhiệm vụ'; form.append(save);
  form.onsubmit=async e=>{e.preventDefault();try {const payload=Object.fromEntries(new FormData(form)); payload.target_count=Number(payload.target_count);
    await appRequest(`/api/projects/${sourceProject}/tasks${task.id?'/'+task.id:''}`,{method:task.id?'PUT':'POST',body:JSON.stringify(payload)});showToast('Đã lưu nhiệm vụ','success');await loadSourceForms();}catch(error){showToast(error.message,'error');}};
  document.getElementById('taskForms').append(form);
}
document.getElementById('addTask').onclick=()=>taskForm();
loadSourceForms();
