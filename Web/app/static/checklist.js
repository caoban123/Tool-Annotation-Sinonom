const checklistRoot=document.getElementById('deliveryChecklist');
async function loadChecklist(){
  try{
    const report=await appRequest(`/api/qa/checklist?project_id=${checklistRoot.dataset.projectId}`);
    checklistRoot.replaceChildren();
    const heading=document.createElement('h2');heading.className='font-bold text-lg';heading.textContent=report.ready?'Đã đáp ứng checklist tự kiểm tra':'Bản đang làm — còn điều kiện bàn giao chưa đạt';checklistRoot.append(heading);
    const note=document.createElement('p');note.className='text-sm my-3';note.textContent=report.note;checklistRoot.append(note);
    for(const condition of report.conditions){const row=document.createElement('div');row.className='checklist-row';row.dataset.passed=condition.passed;const label=document.createElement('span');label.textContent=condition.label;const status=document.createElement('strong');status.textContent=condition.passed?'Đạt':'Cần bổ sung';row.append(label,status);checklistRoot.append(row);}
    for(const task of report.tasks){const line=document.createElement('p');line.className='text-sm mt-3';line.textContent=`${task.assigned_to} · ${task.scope}: ${task.confirmed}/${task.target} cặp xác nhận`;checklistRoot.append(line);}
    if(report.structure_error){const error=document.createElement('p');error.textContent=report.structure_error;checklistRoot.append(error);}
    const link=document.createElement('a');link.href=`/sources/${checklistRoot.dataset.projectId}`;link.className='source-ref';link.textContent='Bổ sung nguồn và nhiệm vụ';checklistRoot.append(link);
  }catch(error){checklistRoot.textContent=error.message;}
}
loadChecklist();
