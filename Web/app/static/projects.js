// Explicit project deletion; the native modal handles focus trapping and Escape.
(() => {
  const dialog = document.getElementById('deleteProjectDialog');
  if (!dialog) return;
  const cancel = document.getElementById('cancelDeleteProject');
  const confirm = document.getElementById('confirmDeleteProject');
  const error = document.getElementById('deleteProjectError');
  const status = document.getElementById('deleteProjectStatus');
  let selected = null;
  let pending = false;

  document.querySelectorAll('.delete-project-trigger').forEach(button => {
    button.addEventListener('click', () => {
      selected = {button, card: button.closest('[data-project-card]'),
        id: button.dataset.projectId, name: button.dataset.projectName,
        revision: Number(button.dataset.projectRevision)};
      document.getElementById('deleteProjectName').textContent = selected.name;
      error.textContent = status.textContent = '';
      dialog.showModal();
      cancel.focus();
    });
  });
  cancel.addEventListener('click', () => { if (!pending) dialog.close(); });
  dialog.addEventListener('cancel', event => { if (pending) event.preventDefault(); });
  confirm.addEventListener('click', async () => {
    if (!selected || pending) return;
    const project = selected;
    pending = confirm.disabled = cancel.disabled = true;
    error.textContent = '';
    status.textContent = 'Đang xóa dự án…';
    try {
      const response = await fetch(`/api/projects/${encodeURIComponent(project.id)}`, {
        method: 'DELETE', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({confirmation_name: project.name, revision: project.revision})
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(typeof body.detail === 'string' ? body.detail : 'Không thể xóa dự án. Vui lòng thử lại.');
      }
      dialog.close();
      project.card.remove();
      window.showToast?.('Đã xóa dự án.', 'success');
      const remaining = document.querySelector('.delete-project-trigger');
      if (remaining) remaining.focus();
      else window.location.reload(); // Render the existing empty-project state.
    } catch (cause) {
      error.textContent = cause.message;
    } finally {
      pending = confirm.disabled = cancel.disabled = false;
      status.textContent = '';
    }
  });
})();
