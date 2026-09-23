let allAuthorizedUsers = [];
let inviteSearchResults = [];

function showToast(message, type) {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = 'toast ' + (type || '');
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('hide');
    setTimeout(() => toast.remove(), 320);
  }, 2600);
}

async function fetchUsers() {
  const res = await fetch('/users');
  const data = await res.json();
  if (!data.ok) {
throw new Error(data.error || '加载用户失败');
  }
  return data.users || [];
}

function userMatchesFilter(user, filterText) {
  if (!filterText) {
return true;
  }
  const haystack = [
user.name,
user.user_key,
user.open_id,
user.user_id,
  ].filter(Boolean).join(' ').toLowerCase();
  return haystack.includes(filterText.toLowerCase());
}

function renderUserOptions(users) {
  const select = document.getElementById('userSelect');
  const countEl = document.getElementById('userCount');
  const previousValue = select.value;
  const filterText = document.getElementById('userFilter').value.trim();
  const visibleUsers = users.filter((u) => userMatchesFilter(u, filterText));
  select.innerHTML = '<option value="">请选择一个已授权用户</option>';
  visibleUsers.forEach((u) => {
const opt = document.createElement('option');
opt.value = u.user_key || '';
const displayName = u.name || '未命名用户';
const suffix = u.open_id ? ` | ${u.open_id}` : (u.user_id ? ` | ${u.user_id}` : '');
opt.textContent = `${displayName}${suffix}`;
select.appendChild(opt);
  });
  if (visibleUsers.some((u) => u.user_key === previousValue)) {
select.value = previousValue;
  }
  countEl.textContent = String(visibleUsers.length);
}

async function loadUsers() {
  const box = document.getElementById('resultBox');
  try {
const users = await fetchUsers();
allAuthorizedUsers = users;
renderUserOptions(allAuthorizedUsers);
if (!users.length) {
  box.textContent = '当前还没有本地已授权用户，请先点击“新增授权用户”。';
}
  } catch (err) {
box.textContent = '加载用户失败：' + err.message;
  }
}

async function doSearch() {
  const q = document.getElementById('keyword').value.trim();
  const docsTypes = document.getElementById('docsTypes').value.trim();
  const userKey = document.getElementById('userSelect').value.trim();
  const ownerOnly = document.getElementById('ownerOnlyFilter').checked;
  const box = document.getElementById('resultBox');

  if (!q) {
box.textContent = '请先输入搜索关键词 q。';
return;
  }
  if (!userKey) {
box.textContent = '请先选择一个已授权用户，搜索请求必须包含 user_key。';
return;
  }

  const params = new URLSearchParams();
  params.set('q', q);
  if (docsTypes) params.set('docs_types', docsTypes);
  params.set('user_key', userKey);
  if (ownerOnly) params.set('owner_only', '1');

  box.textContent = '搜索中...';
  try {
const res = await fetch('/search?' + params.toString());
const data = await res.json();
if (data.ok) {
  renderSearchResults(data);
} else {
  box.textContent = JSON.stringify(data, null, 2);
}
  } catch (err) {
box.textContent = '搜索失败：' + err.message;
  }
}

async function refreshSelectedUserToken() {
  const userKey = document.getElementById('userSelect').value.trim();
  const box = document.getElementById('resultBox');

  if (!userKey) {
box.textContent = '请先选择一个已授权用户，再刷新 token。';
return;
  }

  box.textContent = '正在刷新 token...';
  try {
const res = await fetch('/users/refresh-token', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ user_key: userKey }),
});
const data = await res.json();
box.textContent = JSON.stringify(data, null, 2);
if (data.ok) {
  await loadUsers();
  document.getElementById('userSelect').value = userKey;
}
  } catch (err) {
box.textContent = '刷新 token 失败：' + err.message;
  }
}

async function refreshAllUserTokens() {
  const box = document.getElementById('resultBox');
  box.textContent = '正在刷新全部用户 token...';
  try {
const res = await fetch('/users/refresh-tokens', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
});
const data = await res.json();
box.textContent = JSON.stringify(data, null, 2);
if (data.ok) {
  await loadUsers();
}
  } catch (err) {
box.textContent = '刷新全部 token 失败：' + err.message;
  }
}

function renderInviteUsers(users) {
  const select = document.getElementById('inviteUserSelect');
  select.innerHTML = '<option value="">请选择一个匹配成员</option>';
  users.forEach((u, index) => {
const opt = document.createElement('option');
opt.value = String(index);
const displayName = u.name || u.en_name || '未命名成员';
const idText = u.open_id || u.user_id || u.email || '';
opt.textContent = `${displayName}${idText ? ' | ' + idText : ''}`;
select.appendChild(opt);
  });
}

function getFileToken(file) {
  return file.token || file.docs_token || file.doc_token || file.obj_token || file.document_id || file.file_token || '';
}

function getFileTitle(file, index) {
  return file.title || file.name || file.docs_name || file.file_name || `搜索结果 ${index + 1}`;
}

function getFileUrl(file) {
  const token = getFileToken(file);
  return file.url || (token ? `https://gemdalesh.feishu.cn/docx/${token}` : '');
}

function renderSearchResults(data) {
  const box = document.getElementById('resultBox');
  box.innerHTML = '';

  const header = document.createElement('div');
  let headerText = `找到 ${data.count || 0} 条结果`;
  if (data.owner_filter_applied) {
headerText = headerText + `（该用户名下；过滤前 ${data.total_before_owner_filter || 0} 条，已剔除他人共享的 ${(data.total_before_owner_filter || 0) - (data.count || 0)} 条）`;
  }
  header.textContent = headerText;
  box.appendChild(header);

  const files = data.files || [];
  if (!files.length) {
const empty = document.createElement('div');
empty.className = 'muted';
empty.textContent = '没有搜索到结果。';
box.appendChild(empty);
  }

  files.forEach((file, index) => {
const card = document.createElement('div');
card.className = 'result-card';

const title = document.createElement('div');
title.className = 'result-title';
title.textContent = getFileTitle(file, index);
card.appendChild(title);

const token = getFileToken(file);
const meta = document.createElement('div');
meta.className = 'result-meta';
meta.textContent = token ? `token: ${token}` : '未返回 token，无法构建链接';
card.appendChild(meta);

const url = getFileUrl(file);
if (url) {
  const link = document.createElement('a');
  link.className = 'result-link';
  link.href = url;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  link.textContent = url;
  card.appendChild(link);
}

box.appendChild(card);
  });

  const details = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = '查看完整 JSON';
  details.appendChild(summary);

  const json = document.createElement('pre');
  json.className = 'result-json';
  json.textContent = JSON.stringify(data, null, 2);
  details.appendChild(json);
  box.appendChild(details);
}

async function loadInviteContacts() {
  const box = document.getElementById('resultBox');
  try {
const res = await fetch('/invite/contacts?limit=500');
const data = await res.json();
if (!data.ok) {
  throw new Error(data.error || '加载通讯录缓存失败');
}
inviteSearchResults = data.users || [];
renderInviteUsers(inviteSearchResults);
  } catch (err) {
box.textContent = '加载通讯录缓存失败：' + err.message;
  }
}

async function refreshInviteContacts() {
  const box = document.getElementById('resultBox');
  box.textContent = '正在刷新通讯录缓存...';
  try {
const res = await fetch('/invite/contacts/refresh', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
});
const data = await res.json();
if (!data.ok) {
  throw new Error(data.error || '刷新通讯录缓存失败');
}
inviteSearchResults = data.users || [];
renderInviteUsers(inviteSearchResults);
box.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
box.textContent = '刷新通讯录缓存失败：' + err.message;
  }
}

async function searchInviteUsers() {
  const keyword = document.getElementById('inviteKeyword').value.trim();
  const box = document.getElementById('resultBox');
  if (!keyword) {
box.textContent = '请先输入用户名关键词。';
return;
  }

  box.textContent = '正在搜索通讯录成员...';
  try {
const res = await fetch('/invite/search-users', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ q: keyword }),
});
const data = await res.json();
if (!data.ok) {
  throw new Error(data.error || '搜索通讯录失败');
}
inviteSearchResults = data.users || [];
renderInviteUsers(inviteSearchResults);
box.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
box.textContent = '搜索通讯录失败：' + err.message;
  }
}

async function sendInvite() {
  const selectedIndex = document.getElementById('inviteUserSelect').value;
  const message = document.getElementById('inviteMessage').value.trim();
  const box = document.getElementById('resultBox');
  const selectedUser = inviteSearchResults[Number(selectedIndex)];

  if (!selectedUser) {
box.textContent = '请先搜索并选择一个通讯录成员。';
return;
  }

  const receiveId = selectedUser.open_id || selectedUser.user_id;
  const receiveIdType = selectedUser.open_id ? 'open_id' : 'user_id';
  if (!receiveId) {
box.textContent = '所选成员没有可用于发送邀请的 open_id 或 user_id。';
return;
  }

  box.textContent = '正在发送授权邀请...';
  try {
const res = await fetch('/invite/send', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    open_id: selectedUser.open_id || '',
    name: selectedUser.name || selectedUser.en_name || '',
    receive_id: receiveId,
    receive_id_type: receiveIdType,
    message,
  }),
});
const data = await res.json();
box.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
box.textContent = '发送授权邀请失败：' + err.message;
  }
}

function renderCaptureTargets(targets) {
  const list = document.getElementById('captureTargetList');
  list.innerHTML = '';
  if (!targets.length) {
const empty = document.createElement('div');
empty.className = 'tiny muted';
empty.textContent = '还没有指定抓取用户，请先在通讯录里搜索并加入。';
list.appendChild(empty);
return;
  }

  targets.forEach((target) => {
const item = document.createElement('div');
item.className = 'member-item';

const main = document.createElement('div');
const name = document.createElement('div');
name.className = 'member-main';
name.textContent = target.name || target.en_name || '未命名用户';
const sub = document.createElement('div');
sub.className = 'member-sub';
sub.textContent = target.open_id || target.user_id || target.target_key || '';
main.appendChild(name);
main.appendChild(sub);

const removeBtn = document.createElement('button');
removeBtn.type = 'button';
removeBtn.className = 'secondary';
removeBtn.textContent = '移除';
removeBtn.addEventListener('click', () => removeCaptureTarget(target.target_key));

item.appendChild(main);
item.appendChild(removeBtn);
list.appendChild(item);
  });
}

async function loadCaptureTargets() {
  const box = document.getElementById('resultBox');
  try {
const res = await fetch('/capture/targets');
const data = await res.json();
if (!data.ok) {
  throw new Error(data.error || '加载抓取用户组失败');
}
renderCaptureTargets(data.targets || []);
  } catch (err) {
box.textContent = '加载抓取用户组失败：' + err.message;
  }
}

async function addCaptureTargetFromSelectedInviteUser() {
  const selectedIndex = document.getElementById('inviteUserSelect').value;
  const box = document.getElementById('resultBox');
  const selectedUser = inviteSearchResults[Number(selectedIndex)];
  if (!selectedUser) {
box.textContent = '请先在通讯录里搜索并选择一个成员。';
return;
  }

  try {
const res = await fetch('/capture/targets', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ user: selectedUser }),
});
const data = await res.json();
if (!data.ok) {
  throw new Error(data.error || '加入抓取用户组失败');
}
box.textContent = JSON.stringify(data, null, 2);
await loadCaptureTargets();
showToast('已加入抓取用户组', 'success');
  } catch (err) {
box.textContent = '加入抓取用户组失败：' + err.message;
  }
}

async function removeCaptureTarget(targetKey) {
  const box = document.getElementById('resultBox');
  try {
const res = await fetch('/capture/targets/' + encodeURIComponent(targetKey), {
  method: 'DELETE',
});
const data = await res.json();
if (!data.ok) {
  throw new Error(data.error || '移除抓取用户失败');
}
box.textContent = JSON.stringify(data, null, 2);
showToast('已移除抓取用户', 'success');
await loadCaptureTargets();
  } catch (err) {
box.textContent = '移除抓取用户失败：' + err.message;
  }
}

function fmtBeijingTime(iso) {
  if (!iso) { return ''; }
  const d = new Date(iso);
  if (isNaN(d.getTime())) { return iso; }
  return d.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
}

async function pollCaptureStatus(box) {
  const maxPolls = 600; // 最多轮询 30 分钟
  for (let i = 0; i < maxPolls; i++) {
await new Promise((resolve) => setTimeout(resolve, 3000));
try {
  const res = await fetch('/capture/status');
  const status = await res.json();
  if (!status.ok) { continue; }
  if (status.running) {
    box.textContent = '抓取进行中… 已等待 ' + ((i + 1) * 3) + ' 秒';
    continue;
  }
  box.textContent = '抓取完成：\n' + JSON.stringify(status.last_run, null, 2);
  const lr = (status.last_run) || {};
  showToast('抓取完成：新建 ' + (lr.created || 0) + '，失败 ' + (lr.failed || 0), (lr.failed > 0) ? 'error' : 'success');
  await loadCaptureFailures();
  return;
} catch (err) { /* keep polling */ }
  }
  box.textContent = '轮询超时（30 分钟），抓取可能仍在后台运行，可稍后查看失败记录。';
}

async function runCaptureNow() {
  const box = document.getElementById('resultBox');
  box.textContent = '抓取已启动，每 3 秒轮询一次状态…';
  try {
const res = await fetch('/capture/run', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: '{}',
});
const data = await res.json();
if (!data.ok) {
  box.textContent = JSON.stringify(data, null, 2);
  return;
}
showToast('抓取已启动，后台执行中…');
await pollCaptureStatus(box);
  } catch (err) {
box.textContent = '抓取失败：' + err.message;
  }
}

let captureFailureRuns = [];
let captureFailureShowAll = false;

function renderCaptureFailureRunOptions() {
  const select = document.getElementById('captureFailureRunSelect');
  select.innerHTML = '';
  if (!captureFailureRuns.length) {
const option = document.createElement('option');
option.value = '';
option.textContent = '没有失败轮次';
select.appendChild(option);
select.disabled = true;
return;
  }
  select.disabled = false;
  captureFailureRuns.forEach((run, index) => {
const option = document.createElement('option');
option.value = String(index);
const count = (run.failures || []).length;
option.textContent = fmtBeijingTime(run.run_started_at).slice(5) + ' ｜ 失败 ' + count + ' 条';
select.appendChild(option);
  });
}

function renderCaptureFailures() {
  const list = document.getElementById('captureFailureList');
  list.innerHTML = '';
  if (!captureFailureRuns.length) {
const empty = document.createElement('div');
empty.className = 'tiny muted';
empty.textContent = '最近几轮抓取没有失败记录。';
list.appendChild(empty);
return;
  }
  const select = document.getElementById('captureFailureRunSelect');
  const index = Number(select.value || '0') || 0;
  const run = captureFailureRuns[index] || captureFailureRuns[0];
  const failures = run.failures || [];
  const limit = captureFailureShowAll ? failures.length : 10;

  const head = document.createElement('div');
  head.className = 'tiny muted';
  head.textContent = fmtBeijingTime(run.run_started_at) + ' ｜ ' + (run.summary || '');
  list.appendChild(head);

  failures.slice(0, limit).forEach((f) => {
const item = document.createElement('div');
item.className = 'member-item';
const main = document.createElement('div');
const name = document.createElement('div');
name.className = 'member-main badge-' + (f.scope || 'file');
let label = '[' + (f.scope || '?') + '] ' + (f.target_name || '');
if (f.title) { label = label + ' — ' + f.title; }
name.textContent = label;
const sub = document.createElement('div');
sub.className = 'member-sub';
sub.textContent = f.error || '';
main.appendChild(name);
main.appendChild(sub);
item.appendChild(main);
list.appendChild(item);
  });

  if (failures.length > 10) {
const more = document.createElement('button');
more.type = 'button';
more.className = 'secondary';
more.style.marginTop = '8px';
more.textContent = captureFailureShowAll
  ? '收起，只显示前 10 条'
  : '显示全部 ' + failures.length + ' 条';
more.addEventListener('click', () => {
  captureFailureShowAll = !captureFailureShowAll;
  renderCaptureFailures();
});
list.appendChild(more);
  }
}

async function loadCaptureFailures() {
  const list = document.getElementById('captureFailureList');
  try {
const res = await fetch('/capture/failures?limit=5');
const data = await res.json();
if (!data.ok) {
  throw new Error(data.error || '加载失败记录失败');
}
captureFailureRuns = data.runs_with_failures || [];
captureFailureShowAll = false;
renderCaptureFailureRunOptions();
renderCaptureFailures();
  } catch (err) {
list.innerHTML = '';
const empty = document.createElement('div');
empty.className = 'tiny muted';
empty.textContent = '加载失败记录失败：' + err.message;
list.appendChild(empty);
  }
}

function renderFolderTokenStatus(status) {
  const text = status.configured
? '已配置（来源：' + (status.source === 'frontend' ? '前端设置' : '环境变量') + '，' + (status.masked_token || '') + '）'
: '未配置（抓取不会执行复制）';
  const el1 = document.getElementById('captureFolderStatus');
  const el2 = document.getElementById('folderTokenStatus');
  if (el1) { el1.textContent = text; }
  if (el2) { el2.textContent = text; }
}

async function loadCaptureSettings() {
  try {
const res = await fetch('/capture/settings');
const data = await res.json();
if (!data.ok) {
  throw new Error(data.error || '加载设置失败');
}
renderFolderTokenStatus(data);
  } catch (err) {
const el = document.getElementById('captureFolderStatus');
if (el) { el.textContent = '加载失败：' + err.message; }
  }
}

function extractFolderToken(raw) {
  let value = (raw || '').trim();
  if (value.indexOf('/') >= 0) {
const parts = value.split('?')[0].split('#')[0].split('/');
value = parts[parts.length - 1] || '';
  }
  return value;
}

async function saveCaptureFolderToken() {
  const box = document.getElementById('resultBox');
  const token = extractFolderToken(document.getElementById('folderTokenInput').value);
  if (!token) {
box.textContent = '请输入目标文件夹 token，或直接粘贴文件夹链接。';
return;
  }
  let oldDesc = '未配置';
  try {
const res = await fetch('/capture/settings');
const status = await res.json();
if (status.ok && status.configured) {
  oldDesc = status.masked_token || '';
}
  } catch (err) { /* ignore status fetch errors */ }
  if (!window.confirm('确认修改抓取目标文件夹？\n当前：' + oldDesc + '\n新的：' + token + '\n\n保存前会在目标文件夹创建一篇验证文档。')) {
return;
  }
  try {
const res = await fetch('/capture/settings/folder-token', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ folder_token: token, confirm: true }),
});
const data = await res.json();
box.textContent = JSON.stringify(data, null, 2);
if (data.ok) {
  document.getElementById('folderTokenInput').value = '';
  showToast('目标文件夹已校验并保存', 'success');
  document.getElementById('folderTokenConfirm').checked = false;
  document.getElementById('saveFolderTokenBtn').disabled = true;
  await loadCaptureSettings();
}
  } catch (err) {
box.textContent = '保存失败：' + err.message;
  }
}

async function cloneDocumentToFolder() {
  const userKey = document.getElementById('userSelect').value.trim();
  const sourceDocumentId = document.getElementById('sourceDocumentId').value.trim();
  const targetFolderToken = document.getElementById('cloneFolderToken').value.trim();
  const title = document.getElementById('cloneTitle').value.trim();
  const box = document.getElementById('resultBox');

  if (!userKey) {
box.textContent = '请先选择一个已授权用户。';
return;
  }
  if (!sourceDocumentId) {
box.textContent = '请先输入源文档 document_id。';
return;
  }
  if (!targetFolderToken) {
box.textContent = '请先输入目标 folder token。';
return;
  }

  box.textContent = '正在读取源文档并创建新文档...';
  try {
const res = await fetch('/docx/clone-plain-text', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    user_key: userKey,
    source_document_id: sourceDocumentId,
    target_folder_token: targetFolderToken,
    title,
  }),
});
const data = await res.json();
box.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
box.textContent = '复制文档失败：' + err.message;
  }
}

async function autoFillCloneTitle() {
  const userKey = document.getElementById('userSelect').value.trim();
  const sourceDocumentId = document.getElementById('sourceDocumentId').value.trim();
  const titleInput = document.getElementById('cloneTitle');

  if (!userKey || !sourceDocumentId) {
return;
  }

  // 如果用户已经手动输入了标题，不要覆盖
  if (titleInput.value.trim()) {
return;
  }

  try {
const params = new URLSearchParams();
params.set('user_key', userKey);
params.set('source_document_id', sourceDocumentId);
const res = await fetch('/docx/minutes-meta?' + params.toString());
const data = await res.json();
if (data.ok && data.meta && data.meta.suggested_filename) {
  titleInput.value = data.meta.suggested_filename;
}
  } catch (err) {
// 静默失败，不打扰用户
console.error('获取建议标题失败:', err);
  }
}

document.getElementById('sourceDocumentId').addEventListener('blur', autoFillCloneTitle);
document.getElementById('userSelect').addEventListener('change', autoFillCloneTitle);

document.getElementById('refreshUsersBtn').addEventListener('click', loadUsers);
document.getElementById('searchInviteUsersBtn').addEventListener('click', searchInviteUsers);
document.getElementById('refreshContactsBtn').addEventListener('click', refreshInviteContacts);
document.getElementById('sendInviteBtn').addEventListener('click', sendInvite);
document.getElementById('addCaptureTargetBtn').addEventListener('click', addCaptureTargetFromSelectedInviteUser);
document.getElementById('runCaptureBtn').addEventListener('click', runCaptureNow);
document.getElementById('refreshCaptureTargetsBtn').addEventListener('click', loadCaptureTargets);
document.getElementById('refreshCaptureFailuresBtn').addEventListener('click', loadCaptureFailures);
document.getElementById('captureFailureRunSelect').addEventListener('change', () => {
  captureFailureShowAll = false;
  renderCaptureFailures();
});
document.getElementById('folderTokenConfirm').addEventListener('change', (event) => {
  document.getElementById('saveFolderTokenBtn').disabled = !event.target.checked;
});
document.getElementById('saveFolderTokenBtn').addEventListener('click', saveCaptureFolderToken);
document.getElementById('searchBtn').addEventListener('click', doSearch);
document.getElementById('refreshTokenBtn').addEventListener('click', refreshSelectedUserToken);
document.getElementById('refreshAllTokensBtn').addEventListener('click', refreshAllUserTokens);
document.getElementById('cloneDocBtn').addEventListener('click', cloneDocumentToFolder);
document.getElementById('fillExampleBtn').addEventListener('click', () => {
  document.getElementById('keyword').value = '文字记录';
  document.getElementById('docsTypes').value = 'doc';
});
document.querySelectorAll('[data-copy-target]').forEach((btn) => {
  btn.addEventListener('click', async () => {
const target = document.getElementById(btn.dataset.copyTarget);
if (!target) return;
const oldText = btn.textContent;
const markCopied = () => {
  showToast('已复制到剪贴板', 'success');
  btn.textContent = '已复制';
  setTimeout(() => { btn.textContent = oldText; }, 1200);
};
try {
  if (!navigator.clipboard) {
    throw new Error('Clipboard API unavailable');
  }
  await navigator.clipboard.writeText(target.value);
  markCopied();
} catch (err) {
  target.focus();
  target.select();
  if (document.execCommand('copy')) {
    markCopied();
  } else {
    btn.textContent = '复制失败';
    setTimeout(() => { btn.textContent = oldText; }, 1600);
  }
}
  });
});

loadUsers();
loadInviteContacts();
loadCaptureTargets();
loadCaptureFailures();
loadCaptureSettings();
