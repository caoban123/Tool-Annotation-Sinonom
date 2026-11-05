window.appRequest = async function(url, options={}) {
  const isForm=options.body instanceof FormData;
  const response=await fetch(url,{...options,headers:{...(isForm?{}:{'Content-Type':'application/json'}),...(options.headers||{})}});
  if(!response.ok){let message;try{const data=await response.json();message=typeof data.detail==='string'?data.detail:JSON.stringify(data.detail);}catch{message=response.statusText;}throw new Error(message||'Không thể xử lý yêu cầu');}
  return response.json();
};
document.addEventListener('DOMContentLoaded',()=>{
  document.querySelectorAll('header nav a').forEach(link=>{
    const active=new URL(link.href).pathname===location.pathname;
    if(active){link.setAttribute('aria-current','page');const nav=link.parentElement;requestAnimationFrame(()=>{if(nav.scrollWidth>nav.clientWidth)nav.scrollLeft=link.offsetLeft-nav.offsetLeft-nav.clientWidth/2+link.offsetWidth/2;});}
    else{link.classList.remove('bg-emerald-600','text-white');link.classList.add('text-slate-600');}
  });
  // Give every control an accessible label, including inherited icon buttons.
  document.querySelectorAll('button').forEach(button=>{if(!button.textContent.trim()||button.textContent.trim()==='×')button.setAttribute('aria-label',button.title||'Đóng');});
  document.querySelectorAll('input,textarea,select').forEach((control,index)=>{
    if(control.type==='hidden'||control.closest('label')||control.labels?.length)return;
    const label=control.previousElementSibling;
    control.id ||= `field-${index}`;
    if(label?.tagName==='LABEL')label.htmlFor=control.id;
    else if(!control.hasAttribute('aria-label'))control.setAttribute('aria-label',control.placeholder||control.name||'Nội dung');
  });
  let activeModal=null, previousFocus=null;
  const modals=[...document.querySelectorAll('[id$="Modal"]')];
  function syncModal(){
    const visible=modals.find(modal=>!modal.classList.contains('hidden'))||null;
    if(visible===activeModal)return;
    if(visible){
      previousFocus=document.activeElement;window.pendingCardFocus=previousFocus?.closest('[id^="card_"]')?.id;
      visible.setAttribute('role','dialog');visible.setAttribute('aria-modal','true');
      const title=visible.querySelector('h2,h3');if(title){title.id||=`${visible.id}-title`;visible.setAttribute('aria-labelledby',title.id);}
      activeModal=visible;document.body.classList.add('modal-open');
      const target=visible.querySelector('textarea,input:not([type=hidden]),select')||visible.querySelector('button');target?.focus();
    }else{
      activeModal=null;document.body.classList.remove('modal-open');
      if(previousFocus?.isConnected)previousFocus.focus();
      else if(window.pendingCardFocus)document.getElementById(window.pendingCardFocus)?.focus();
    }
  }
  const observer=new MutationObserver(syncModal);modals.forEach(modal=>observer.observe(modal,{attributes:true,attributeFilter:['class']}));
  document.addEventListener('keydown',event=>{
    if(!activeModal)return;
    if(event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();activeModal.classList.add('hidden');return;}
    if(event.key==='Tab'){
      const items=[...activeModal.querySelectorAll('button,input:not([type=hidden]),textarea,select,a[href],[tabindex="0"]')].filter(item=>!item.disabled&&item.getClientRects().length);
      if(!items.length)return;
      const first=items[0],last=items.at(-1);
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
    }
  },true);
  document.addEventListener('focusin',event=>{if(activeModal&&!activeModal.contains(event.target))activeModal.querySelector('button,input,textarea')?.focus();});
});
