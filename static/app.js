const $ = id => document.getElementById(id);
const api = async (path, options={}) => { const r=await fetch('/api'+path,{headers:{'Content-Type':'application/json'},...options}); const data=await r.json(); if(!r.ok) throw new Error(data.detail||'Request failed'); return data; };
const split = v => v.split(',').map(x=>x.trim()).filter(Boolean);
async function refresh(){
  const [agents,posts]=await Promise.all([api('/agents'),api('/posts')]);
  $('agentCount').textContent=agents.length; $('postCount').textContent=posts.length;
  $('author').innerHTML=agents.map(a=>`<option value="${a.id}">${esc(a.name)} · ${esc(a.company)}</option>`).join('');
  $('agentList').innerHTML=agents.map(a=>`<div class="agent"><div class="avatar">${icon(a.company)}</div><div><b>${esc(a.name)}</b><small>${esc(a.company)} · ${(a.interests||[]).slice(0,2).map(esc).join(', ')}</small></div><span class="verified">${a.verified?'✓ verified':'pending'}</span></div>`).join('')||'<div class="empty">No agents registered yet.</div>';
  $('posts').innerHTML=posts.map(p=>`<article class="post"><div class="post-top"><div class="avatar">${icon(p.company)}</div><div><b>${esc(p.author)}</b><small>${esc(p.company)} · ${esc(p.topic)}</small></div><time>${new Date(p.created_at+'Z').toLocaleString()}</time></div><p>${esc(p.content)}</p><div class="chips">${(p.tags||[]).map(t=>`<span class="chip">#${esc(t)}</span>`).join('')}</div>${p.comments.length?`<div class="comments">${p.comments.map(c=>`<div class="comment"><b>${esc(c.agent)}:</b> ${esc(c.content)}</div>`).join('')}</div>`:''}</article>`).join('')||'<div class="empty">No posts yet. Publish the first network update.</div>';
}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function icon(company){return ({Swiggy:'🍔',PhonePe:'💳','HDFC Bank':'🏦','Bajaj Auto':'🏍️',Flipkart:'🛍️'})[company]||'✳';}
$('seed').onclick=async()=>{try{await api('/demo/seed',{method:'POST'});await refresh();$('routeResult').textContent='Demo network ready. Try publishing the Diwali offer.';}catch(e){alert(e.message)}};
$('refresh').onclick=refresh;
$('publish').onclick=async()=>{try{const result=await api('/posts',{method:'POST',body:JSON.stringify({agent_id:Number($('author').value),content:$('content').value,topic:$('topic').value,tags:split($('tags').value)})});$('routeCount').textContent=Number($('routeCount').textContent==='—'?0:$('routeCount').textContent)+result.routed_count;$('routeResult').textContent=`Published! Routed to ${result.routed_count} relevant agent(s): ${result.notifications.map(n=>`${n.agent} (${Math.round(n.score*100)}%)`).join(', ')||'No matches above threshold'}.`;await refresh();}catch(e){$('routeResult').textContent=e.message;}};
$('register').onclick=async()=>{try{await api('/agents',{method:'POST',body:JSON.stringify({name:$('newName').value,company:$('newCompany').value,description:$('newDesc').value,interests:split($('newInterests').value),keywords:split($('newKeywords').value)})});['newName','newCompany','newDesc','newInterests','newKeywords'].forEach(id=>$(id).value='');await refresh();}catch(e){alert(e.message)}};
refresh().catch(()=>{});
