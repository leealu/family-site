const $ = (s) => document.querySelector(s);
const authDialog = $("#authDialog");
const contentDialog = $("#contentDialog");
const authForm = $("#authForm");
let view = {setupRequired:true, authenticated:false, records:[], content:null};
let editingRecordId = null;
let diaryPage = 0;
let diarySort = "date";
let recordMedia = [];
const diaryMediaPages = new Map();
const interestMediaPages = new Map();
let sessionExpiryTimer = null;
let lightboxRecordId = null;
let lightboxGalleryKind = "diary";
let lightboxIndex = 0;
let diaryEditorOpen = false;
let activeAdminTab = "content";
let musicSources = [];

const CONTENT_DEFAULTS = {
  siteName:"kani的奇妙小世界",logoEmoji:"🌼",navDiary:"成长日记",navLikes:"兴趣角",heroBadge:"🎈 3 岁半的小小探险家",heroLine1:"你好呀！",heroLine2:"欢迎来到",heroLine3:"我的小世界",heroEmoji:"☀️",heroMascot:"🐻",heroDescription:"这里有我喜欢的东西、每天的新发现，还有一点点长大的故事。牵好大人的手，一起来逛逛吧！",heroButton:"翻开成长日记",float1:"🌷 你好朋友！",float2:"✨ 今天也有新发现",float3:"🧸 抱抱时间",
  profile:[{icon:"🧸",title:"我的年龄",text:"3 岁半啦，正在长大"},{icon:"💛",title:"我喜欢",text:"画画 · 故事 · 唱唱跳跳"},{icon:"🌱",title:"每天一点点",text:"发现新东西，学会新本领"}],
  likesEyebrow:"MY FAVORITE THINGS",likesTitle:"我的兴趣角 🎨",likesDescription:"喜欢的事情，就像口袋里的小星星。",interests:[{icon:"🖍️",title:"画画涂颜色",description:"拿起蜡笔，把脑袋里的奇妙想法画出来。",tag:"我的小画家时光"},{icon:"📚",title:"听故事时间",description:"翻开绘本，和小动物一起去冒险。",tag:"再讲一个嘛！"},{icon:"🎵",title:"唱歌蹦蹦跳",description:"听到喜欢的音乐，身体就忍不住动起来。",tag:"啦啦啦～"}],
  diaryEyebrow:"LITTLE GROWING MOMENTS",diaryTitle:"成长日记 📔",diaryDescription:"把平凡日子里的小小进步，收藏起来。",diaryCardEyebrow:"我的小小记录本",diaryIcon:"📒",diaryCardTitle:"今天，我又长大一点点啦！",diaryCardDescription:"这里记录第一次尝试的新事情、最近学会的小本领，或一句可爱的童言童语。家长登录后，就可以添加和管理成长记录。",loginCta:"家长登录后添加",recordFormTitle:"记下一个小瞬间 ✨",recordDateLabel:"日期",recordTitleLabel:"小标题",recordStoryLabel:"成长故事",recordTitlePlaceholder:"比如：第一次自己穿上鞋子",recordStoryPlaceholder:"写下今天的小发现、童言童语或学会的新本领……",recordSaveButton:"保存记录",recordCancelButton:"取消修改",emptyRecords:"还没有成长记录，添加第一条小故事吧 🌷",footerLeft:"每天都有新发现，慢慢长大真奇妙！ 🌈",footerRight:"家庭小天地 · 请和大人一起浏览"
};

function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g,(c)=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
async function api(path, options={}) {
  const response = await fetch(path,{credentials:"same-origin",headers:{"Content-Type":"application/json",...(options.headers||{})},...options});
  const data = await response.json().catch(()=>({}));
  if(response.status===401&&view.authenticated)window.location.reload();
  if(!response.ok) throw new Error(data.error||"暂时无法完成操作，请稍后再试。");
  return data;
}
function openAuth() {
  $("#authTitle").textContent=view.setupRequired?"设置家长账号":"家长登录";
  $("#authHint").textContent=view.setupRequired?"创建一个家长账号，邮箱只在这里填写一次。请使用至少 12 位密码。":"输入家长密码即可登录。";
  $("#authSubmit").textContent=view.setupRequired?"创建账号":"登录";
  $("#nameField").hidden=!view.setupRequired;
  authForm.elements.name.required=view.setupRequired;
  authForm.elements.password.autocomplete=view.setupRequired?"new-password":"current-password";
  authForm.elements.email.required=view.setupRequired;
  authForm.elements.email.closest("label").hidden=!view.setupRequired;
  $("#authError").textContent="";authDialog.showModal();
}
function setText(id,value){const el=$("#"+id);if(el)el.textContent=value??"";}
function applyContent(content) {
  content=content||CONTENT_DEFAULTS;
  document.title=content.siteName;
  for(const key of ["siteName","logoEmoji","navDiary","navLikes","heroBadge","heroLine1","heroLine2","heroLine3","heroEmoji","heroDescription","heroButton","float1","float2","float3","likesEyebrow","likesTitle","likesDescription","diaryEyebrow","diaryTitle","diaryDescription","footerLeft","footerRight"])setText(key,content[key]);
  const mascot=$("#heroMascot"),mascotValue=String(content.heroMascot||"🐻");
  if(/^\/media\/[a-f0-9]{32}\.(?:jpg|jpeg|png|webp|gif)$/.test(mascotValue)){const image=document.createElement("img");image.src=mascotValue;image.alt="主页主角头像";mascot.replaceChildren(image);mascot.classList.add("has-image");}
  else{mascot.textContent=mascotValue;mascot.classList.remove("has-image");}
  const profile=Array.isArray(content.profile)?content.profile:CONTENT_DEFAULTS.profile;
  $("#profileCards").innerHTML=profile.map((item)=>`<div class="info"><span class="ico">${escapeHtml(item.icon)}</span><div><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.text)}</small></div></div>`).join("");
  renderInterestCards(content);
}
function renderInterestCards(content=view.content||CONTENT_DEFAULTS){
  const interests=Array.isArray(content.interests)?content.interests:CONTENT_DEFAULTS.interests;
  $("#interestCards").innerHTML=interests.map((item,index)=>`<article class="card"><div class="picture bg${index%3+1}">${escapeHtml(item.icon)}</div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.description)}</p><span class="chip">${escapeHtml(item.tag)}</span>${item.media?.length?`<div class="interest-media">${renderInterestGallery(item,index)}</div>`:""}</article>`).join("");
  bindGalleryControls($("#interestCards"));
  bindProviderPlay($("#interestCards"));
}
function renderPublicMedia(asset){
  const title=escapeHtml(asset.title||asset.name||"");
  if(asset.type==="image")return `<figure><img src="${escapeHtml(asset.url)}" alt="${title||"兴趣作品"}" loading="lazy">${title?`<figcaption>${title}</figcaption>`:""}</figure>`;
  if(asset.type==="video")return `<figure><video controls playsinline preload="metadata" src="${escapeHtml(asset.url)}"></video>${title?`<figcaption>${title}</figcaption>`:""}</figure>`;
  if(asset.type==="audio")return `<div class="audio-item"><strong>${title||"故事音频"}</strong><audio controls preload="none" src="${escapeHtml(asset.url)}"></audio></div>`;
  if(asset.type==="netease")return `<a class="netease-link" href="${escapeHtml(asset.url)}" target="_blank" rel="noopener noreferrer"><span>🎧</span><span><strong>${title||"网易云故事专辑"}</strong><small>打开网易云音乐播放 ↗</small></span></a>`;
  if(asset.type==="provider-track")return `<div class="provider-track">${asset.track?.coverUrl?`<img src="${escapeHtml(asset.track.coverUrl)}" alt="" loading="lazy">`:`<span class="provider-track-icon">🎧</span>`}<div class="provider-track-info"><strong>${escapeHtml(asset.track?.title||title||"在线音频")}</strong><small>${escapeHtml([asset.track?.creator,asset.track?.providerName].filter(Boolean).join(" · "))}</small><span class="provider-track-player"><button type="button" class="provider-play" data-play-track="${escapeHtml(asset.savedItemKey)}">▶ 播放</button><span role="status"></span></span></div></div>`;
  return "";
}
function bindProviderPlay(root){
  root.querySelectorAll("[data-play-track]").forEach((button)=>button.addEventListener("click",async()=>{
    const status=button.parentElement.querySelector('[role="status"]');button.disabled=true;status.textContent="正在连接音源…";
    try{const result=await api(`/api/music/play/${encodeURIComponent(button.dataset.playTrack)}`,{headers:{}});const audio=document.createElement("audio");audio.controls=true;audio.preload="none";audio.src=result.url;button.replaceWith(audio);status.textContent="";audio.play().catch(()=>{status.textContent="请再点一次播放。";});}
    catch(error){button.disabled=false;status.textContent=error.message;}
  }));
}
async function prepareImageForUpload(file){
  const ext=file.name.split(".").pop().toLowerCase();
  if(ext==="gif"||ext==="webp"||file.type==="image/gif"||file.type==="image/webp")return file;
  if(!file.type.startsWith("image/")&&!['jpg','jpeg','png','webp','heic','heif'].includes(ext))return file;
  const sourceUrl=URL.createObjectURL(file);
  try{
    const image=new Image();image.decoding="async";image.src=sourceUrl;
    await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(new Error("这张图片无法在当前浏览器中读取；请将 iPhone 的相机格式设为“兼容性最佳”后重试。"));});
    const scale=Math.min(1,1920/Math.max(image.naturalWidth,image.naturalHeight));
    const canvas=document.createElement("canvas");canvas.width=Math.max(1,Math.round(image.naturalWidth*scale));canvas.height=Math.max(1,Math.round(image.naturalHeight*scale));
    const context=canvas.getContext("2d");if(!context)throw new Error("无法压缩图片，请重试。");context.drawImage(image,0,0,canvas.width,canvas.height);
    const blob=await new Promise((resolve)=>canvas.toBlob(resolve,"image/webp",0.82));if(!blob||blob.type!=="image/webp")throw new Error("浏览器暂不支持 WebP 编码，请更新浏览器后重试。");
    const base=file.name.replace(/\.[^.]+$/,"")||"photo";return new File([blob],`${base}.webp`,{type:"image/webp",lastModified:Date.now()});
  }finally{URL.revokeObjectURL(sourceUrl);}
}
function newUploadId(){const bytes=new Uint8Array(16);crypto.getRandomValues(bytes);return Array.from(bytes,(value)=>value.toString(16).padStart(2,"0")).join("");}
async function uploadMediaFile(sourceFile,onProgress=()=>{}){
  if(sourceFile.size>200*1024*1024)throw new Error(`${sourceFile.name} 超过 200 MiB。`);
  const file=await prepareImageForUpload(sourceFile);if(file.size>200*1024*1024)throw new Error(`${file.name} 超过 200 MiB。`);
  const request=async(url,options)=>{const response=await fetch(url,{credentials:"same-origin",...options});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error||`上传失败（HTTP ${response.status}）。`);return data;};
  if(file.size<=80*1024*1024){onProgress("正在上传…");return request(`/api/media?filename=${encodeURIComponent(file.name)}`,{method:"POST",headers:{"Content-Type":file.type||"application/octet-stream"},body:file});}
  const chunkSize=8*1024*1024,parts=Math.ceil(file.size/chunkSize),id=newUploadId();
  for(let part=0;part<parts;part++){
    const body=file.slice(part*chunkSize,Math.min(file.size,(part+1)*chunkSize));onProgress(`正在传输第 ${part+1}/${parts} 段…`);let lastError;
    for(let attempt=0;attempt<3;attempt++){try{await request(`/api/media/chunk?id=${id}&filename=${encodeURIComponent(file.name)}&part=${part}&parts=${parts}`,{method:"POST",headers:{"Content-Type":"application/octet-stream"},body});lastError=null;break;}catch(error){lastError=error;if(attempt<2)await new Promise((resolve)=>setTimeout(resolve,500*(attempt+1)));}}
    if(lastError)throw new Error(`${file.name} 第 ${part+1} 段上传失败：${lastError.message}`);
  }
  onProgress("正在合并文件…");return request(`/api/media/finish?id=${id}`,{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
}
function renderDiaryMedia(asset){
  const title=escapeHtml(asset.title||asset.name||"");
  if(asset.type==="image")return `<figure><img src="${escapeHtml(asset.url)}" alt="${title||"成长记录照片"}" loading="lazy">${title?`<figcaption>${title}</figcaption>`:""}</figure>`;
  if(asset.type==="video")return `<figure><video controls playsinline preload="metadata" src="${escapeHtml(asset.url)}"></video>${title?`<figcaption>${title}</figcaption>`:""}</figure>`;
  return "";
}
function galleryPayload(kind,key){
  if(kind==="diary"){const record=(view.records||[]).find((item)=>item.id===key);return record?{items:record.media||[],title:record.title}:null;}
  const item=(view.content?.interests||[])[Number(key)];return item?{items:item.media||[],title:item.title}:null;
}
function galleryPageStore(kind){return kind==="diary"?diaryMediaPages:interestMediaPages;}
function renderGallerySlide(asset,kind,key,index,title){
  const label=escapeHtml(asset.title||asset.name||title||"成长记录照片");
  if(asset.type==="image")return `<button type="button" class="gallery-open" data-open-gallery="${index}" data-gallery-kind="${kind}" data-gallery-key="${escapeHtml(key)}" aria-label="放大查看${label}"><img src="${escapeHtml(asset.url)}" alt="${label}" loading="lazy"><span>⤢ 点开看大图</span></button>`;
  if(asset.type==="video")return `<div class="gallery-video-wrap"><video controls playsinline preload="metadata" src="${escapeHtml(asset.url)}"></video><button type="button" class="gallery-expand" data-open-gallery="${index}" data-gallery-kind="${kind}" data-gallery-key="${escapeHtml(key)}" aria-label="放大播放${label}">⤢</button></div>`;
  if(asset.type==="audio")return `<div class="gallery-audio"><strong>🎵 ${label}</strong><audio controls preload="none" src="${escapeHtml(asset.url)}"></audio></div>`;
  if(asset.type==="netease")return `<a class="gallery-netease" href="${escapeHtml(asset.url)}" target="_blank" rel="noopener noreferrer"><span>🎧</span><strong>${label}</strong><small>打开网易云音乐播放 ↗</small></a>`;
  if(asset.type==="provider-track")return `<div class="gallery-provider-track"><span>🎧</span><strong>${escapeHtml(asset.track?.title||label)}</strong><small>${escapeHtml([asset.track?.creator,asset.track?.providerName].filter(Boolean).join(" · "))}</small><button type="button" class="provider-play" data-play-track="${escapeHtml(asset.savedItemKey)}">▶ 播放</button><span role="status"></span></div>`;
  return "";
}
function renderPagedGallery(media,kind,key,title){
  if(!media?.length)return "";
  const store=galleryPageStore(kind),page=Math.min(Math.max(0,store.get(key)||0),media.length-1);store.set(key,page);
  const safeKey=escapeHtml(key),safeTitle=escapeHtml(title);
  return `<section class="diary-gallery ${media.length>1?"is-stack":""}" aria-label="${safeTitle} 相册" data-count="${media.length}"><div class="gallery-frame"><div class="gallery-slide">${renderGallerySlide(media[page],kind,key,page,title)}${media[page].title||media[page].name?`<span class="gallery-caption">${escapeHtml(media[page].title||media[page].name)}</span>`:""}</div>${media.length>1?`<button type="button" class="gallery-nav gallery-prev" data-gallery-step="-1" data-gallery-kind="${kind}" data-gallery-key="${safeKey}" aria-label="上一张" ${page===0?"disabled":""}>‹</button><button type="button" class="gallery-nav gallery-next" data-gallery-step="1" data-gallery-kind="${kind}" data-gallery-key="${safeKey}" aria-label="下一张" ${page>=media.length-1?"disabled":""}>›</button><span class="gallery-counter">${page+1} / ${media.length}</span>`:""}</div>${media.length>1?`<div class="gallery-dots" aria-label="选择照片">${media.map((_,index)=>`<button type="button" data-gallery-to="${index}" data-gallery-kind="${kind}" data-gallery-key="${safeKey}" class="${index===page?"active":""}" aria-label="第 ${index+1} 张"></button>`).join("")}</div>`:""}</section>`;
}
function renderDiaryGallery(record){
  return renderPagedGallery(record.media||[],"diary",record.id,record.title);
}
function renderInterestGallery(item,index){
  return renderPagedGallery(item.media||[],"interest",String(index),item.title);
}
function diaryRecordsInCurrentOrder(){
  const records=[...(view.records||[])];
  const ageMonths=(label)=>{const text=String(label||"");const years=Number(text.match(/(\d+)\s*岁/)?.[1]||0),months=Number(text.match(/(\d+)\s*个?月/)?.[1]||0)+(text.includes("岁半")?6:0);return /\d+\s*岁|\d+\s*个?月/.test(text)?years*12+months:null;};
  if(diarySort==="age")records.sort((a,b)=>{const am=ageMonths(a.age_label),bm=ageMonths(b.age_label);if(am===null&&bm===null)return a.date.localeCompare(b.date);if(am===null)return 1;if(bm===null)return -1;return am-bm||a.date.localeCompare(b.date);});
  else records.sort((a,b)=>a.date.localeCompare(b.date)||String(a.created_at||"").localeCompare(String(b.created_at||"")));
  return records;
}
function updateDiaryLightbox(){
  const dialog=$("#diaryLightbox"),gallery=galleryPayload(lightboxGalleryKind,lightboxRecordId);
  if(!dialog||!gallery?.items.length){dialog?.close();return;}
  lightboxIndex=Math.max(0,Math.min(lightboxIndex,gallery.items.length-1));
  const asset=gallery.items[lightboxIndex],stage=$("#lightboxStage"),caption=$("#lightboxCaption"),counter=$("#lightboxCounter");
  stage.innerHTML=asset.type==="video"?`<video class="lightbox-media" controls autoplay playsinline src="${escapeHtml(asset.url)}"></video>`:asset.type==="audio"?`<div class="lightbox-audio"><strong>🎵 ${escapeHtml(asset.title||asset.name||gallery.title)}</strong><audio controls autoplay src="${escapeHtml(asset.url)}"></audio></div>`:asset.type==="netease"?`<a class="lightbox-netease" href="${escapeHtml(asset.url)}" target="_blank" rel="noopener noreferrer">🎧 ${escapeHtml(asset.title||gallery.title)}<small>打开网易云音乐播放 ↗</small></a>`:`<img class="lightbox-media" src="${escapeHtml(asset.url)}" alt="${escapeHtml(asset.title||asset.name||gallery.title)}">`;
  caption.textContent=asset.title||asset.name||gallery.title;counter.textContent=`${lightboxIndex+1} / ${gallery.items.length}`;
  $("#lightboxPrevious").hidden=gallery.items.length<2;$("#lightboxNext").hidden=gallery.items.length<2;
  $("#lightboxPrevious").disabled=lightboxIndex===0;$("#lightboxNext").disabled=lightboxIndex>=gallery.items.length-1;
}
function openDiaryLightbox(kind,key,index){lightboxGalleryKind=kind;lightboxRecordId=key;lightboxIndex=index;updateDiaryLightbox();$("#diaryLightbox").showModal();}
function bindGalleryControls(root){
  if(!root)return;
  const rerender=(kind)=>kind==="diary"?renderDiaryBook():renderInterestCards();
  root.querySelectorAll("[data-gallery-step]").forEach((button)=>button.addEventListener("click",()=>{const kind=button.dataset.galleryKind,key=button.dataset.galleryKey,gallery=galleryPayload(kind,key);if(!gallery)return;const store=galleryPageStore(kind);store.set(key,Math.min(Math.max(0,(store.get(key)||0)+Number(button.dataset.galleryStep)),gallery.items.length-1));rerender(kind);}));
  root.querySelectorAll("[data-gallery-to]").forEach((button)=>button.addEventListener("click",()=>{const kind=button.dataset.galleryKind,key=button.dataset.galleryKey,store=galleryPageStore(kind);store.set(key,Number(button.dataset.galleryTo));rerender(kind);}));
  root.querySelectorAll("[data-open-gallery]").forEach((button)=>button.addEventListener("click",()=>openDiaryLightbox(button.dataset.galleryKind,button.dataset.galleryKey,Number(button.dataset.openGallery))));
}
function diaryMediaEditor(){
  return `<section class="record-media-editor"><strong>照片和视频</strong><label class="upload-label">选择照片或视频<input id="recordMediaInput" type="file" multiple accept="image/jpeg,image/png,image/webp,image/gif,image/heic,image/heif,video/mp4,video/webm,video/quicktime"></label><small>静态照片自动压缩为 WebP；GIF 保留动画；每个文件最多 200 MiB。</small><div id="recordMediaList" class="record-media-list"></div><span id="recordMediaStatus" role="status" class="status"></span></section>`;
}
function renderRecordMediaEditor(){
  const list=$("#recordMediaList");if(!list)return;
  list.innerHTML=recordMedia.map((asset,index)=>`<div class="record-media-item"><div>${renderDiaryMedia(asset)}</div><button type="button" class="delete" data-remove-record-media="${index}">移除</button></div>`).join("");
  list.querySelectorAll("[data-remove-record-media]").forEach((button)=>button.onclick=async()=>{const index=Number(button.dataset.removeRecordMedia),asset=recordMedia[index];if(asset?._pending){try{await api(asset.url.replace("/media/","/api/media/"),{method:"DELETE",body:"{}"});}catch(error){$("#recordMediaStatus").textContent=error.message;return;}}recordMedia.splice(index,1);renderRecordMediaEditor();});
}
async function uploadRecordFiles(input){
  const status=$("#recordMediaStatus");input.disabled=true;status.textContent="正在准备照片…";
  try{for(const file of input.files){const data=await uploadMediaFile(file,(message)=>{status.textContent=`${file.name}：${message}`;});if(!["image","video"].includes(data.type))throw new Error("日记仅支持照片和视频。");recordMedia.push({...data,_pending:true});renderRecordMediaEditor();}status.textContent="附件已上传，保存记录后会显示在成长笔记本里。";}
  catch(error){status.textContent=error.message;}finally{input.disabled=false;input.value="";}
}
function diaryIntro() {
  const content=view.content||CONTENT_DEFAULTS;
  return `<div class="diary"><div><div class="label">${escapeHtml(content.diaryCardEyebrow)}</div><h2>${escapeHtml(content.diaryCardTitle)}</h2><p>${escapeHtml(content.diaryCardDescription)}</p></div><span class="diary-pic">${escapeHtml(content.diaryIcon)}</span></div>`;
}
function renderDiaryBook(){
  const book=$("#diaryBook"),sorter=$("#diarySort"),bookmarks=$("#diaryBookmarks");if(!book)return;
  const records=diaryRecordsInCurrentOrder();
  const pageCount=Math.max(1,records.length);diaryPage=Math.min(Math.max(0,diaryPage),pageCount-1);
  const record=records[diaryPage];
  const page=record?`<div class="diary-page-heading"><span>🌷 成长记录</span><span class="diary-page-meta">${record.age_label?`<b>🎂 ${escapeHtml(record.age_label)}</b>`:""}<time>${escapeHtml(record.date)}</time></span></div><div class="diary-page-content"><h3>${escapeHtml(record.title)}</h3><p>${escapeHtml(record.story)}</p>${renderDiaryGallery(record)}</div>`:`<div class="book-empty">${escapeHtml(view.authenticated?(view.content||CONTENT_DEFAULTS).emptyRecords:"小小笔记本还没有记录，期待下一页成长故事 🌷")}</div>`;
  book.innerHTML=`<div class="diary-book-spread"><article class="diary-page" key="${diaryPage}">${page}</article></div><nav class="book-controls" aria-label="成长记录翻页"><button type="button" id="bookPrevious" ${diaryPage===0?"disabled":""}>← 上一页</button><span>${records.length?`第 ${diaryPage+1} / ${records.length} 页`:"暂无记录"}</span><button type="button" id="bookNext" ${diaryPage>=pageCount-1?"disabled":""}>下一页 →</button></nav>`;
  if(sorter){sorter.value=diarySort;sorter.onchange=()=>{diarySort=sorter.value;diaryPage=0;renderDiaryBook();};}
  if(bookmarks){const groups=new Map();records.forEach((item,index)=>{const key=String(item.age_label||"").trim();if(key&&!groups.has(key))groups.set(key,index);});bookmarks.innerHTML=[...groups].map(([label,index])=>`<button type="button" class="age-bookmark ${index===diaryPage?"active":""}" data-page="${index}">🎂 ${escapeHtml(label)}</button>`).join("");bookmarks.querySelectorAll("[data-page]").forEach((button)=>button.addEventListener("click",()=>{diaryPage=Number(button.dataset.page);renderDiaryBook();}));}
  $("#bookPrevious").addEventListener("click",()=>{diaryPage--;renderDiaryBook();});
  $("#bookNext").addEventListener("click",()=>{diaryPage++;renderDiaryBook();});
  bindGalleryControls(book);
}
function render() {
  clearTimeout(sessionExpiryTimer);
  const content=view.content||CONTENT_DEFAULTS;
  applyContent(content);
  const accountButton=$("#accountButton");accountButton.hidden=false;accountButton.textContent=view.authenticated?"退出家长账号":"家长登录";
  const contentButton=$("#contentButton");contentButton.hidden=!view.authenticated;
  if(view.authenticated&&view.sessionExpiresAt){const remaining=Date.parse(view.sessionExpiresAt)-Date.now();sessionExpiryTimer=setTimeout(()=>loadState(),Math.max(0,remaining));}
  const area=$("#diaryArea");
  const diarySection=$("#diary"),navDiary=$("#navDiary");diarySection.hidden=false;navDiary.hidden=false;
  const heroDiaryLink=document.querySelector(".hero-copy > a.button");heroDiaryLink.href="#diary";$("#heroButton").textContent=content.heroButton;
  const diaryLink=area.ownerDocument.querySelector('a[href="#diary"]');if(diaryLink)diaryLink.onclick=null;
  if(navDiary)navDiary.onclick=null;
  area.innerHTML=`${diaryIntro()}<section class="diary-book" aria-label="可翻页成长记事本"><div class="notebook-title"><span>📒</span><div><strong>小小成长笔记本</strong><small>把每个小小的长大瞬间，认真收藏起来</small></div><span class="title-sparkle">✦</span></div><div class="diary-toolbar"><label>翻阅方式<select id="diarySort"><option value="date">按日期</option><option value="age">按年龄阶段</option></select></label><span>点年龄书签，跳到那段成长时光</span></div><nav id="diaryBookmarks" class="diary-bookmarks" aria-label="年龄书签"></nav><div id="diaryBook"></div></section>`;
  renderDiaryBook();
  if(!view.authenticated&&contentDialog.open)contentDialog.close();
  renderDiaryAdmin();
}
async function loadState(){
  try{view=await api("/api/state",{headers:{}});}catch(error){console.error(error);view={setupRequired:true,authenticated:false,records:[],content:CONTENT_DEFAULTS};}
  render();
}
async function saveRecord(event){
  event.preventDefault();const form=event.currentTarget;const button=$("#recordSubmit");button.disabled=true;
  try{const creating=!editingRecordId,payload=Object.fromEntries(new FormData(form).entries());payload.media=recordMedia.map(({type,name,title,url})=>({type,name,title,url}));await api(editingRecordId?`/api/records/${encodeURIComponent(editingRecordId)}`:"/api/records",{method:editingRecordId?"PUT":"POST",body:JSON.stringify(payload)});view=await api("/api/state",{headers:{}});if(creating)diaryPage=0;diaryEditorOpen=false;editingRecordId=null;recordMedia=[];render();setAdminTab("diary");}
  catch(error){$("#recordStatus").textContent=error.message;button.disabled=false;}
}
function diaryRecordFormMarkup(record=null){
  const content=view.content||CONTENT_DEFAULTS;
  return `<form class="add-form diary-admin-form" id="recordForm"><h3>${record?"修改成长记录":"添加成长记录"} ✨</h3><div class="fields"><label>${escapeHtml(content.recordDateLabel)}<input name="date" type="date" required value="${escapeHtml(record?.date||new Date().toLocaleDateString("en-CA"))}"></label><label>成长阶段（选填）<input name="age_label" maxlength="40" value="${escapeHtml(record?.age_label||"")}" placeholder="例如：3岁半、3岁6个月、42个月"></label><label>${escapeHtml(content.recordTitleLabel)}<input name="title" maxlength="100" required value="${escapeHtml(record?.title||"")}" placeholder="${escapeHtml(content.recordTitlePlaceholder)}"></label><label class="fullrow">${escapeHtml(content.recordStoryLabel)}<textarea name="story" maxlength="3000" required placeholder="${escapeHtml(content.recordStoryPlaceholder)}">${escapeHtml(record?.story||"")}</textarea></label></div>${diaryMediaEditor()}<div class="form-actions"><button class="button" type="submit" id="recordSubmit">${record?"保存修改":"保存记录"} <span>♥</span></button><button class="cancel-edit" type="button" id="cancelEdit">取消</button><span id="recordStatus" class="status" role="status"></span></div></form>`;
}
function setAdminTab(tab){
  activeAdminTab=tab;
  $("#adminContentPanel").hidden=tab!=="content";
  $("#adminDiaryPanel").hidden=tab!=="diary";
  $("#adminMusicPanel").hidden=tab!=="music";
  document.querySelectorAll("[data-admin-tab]").forEach((button)=>{const active=button.dataset.adminTab===tab;button.classList.toggle("active",active);button.setAttribute("aria-selected",String(active));});
}
function renderDiaryAdmin(){
  const list=$("#diaryAdminList"),mount=$("#recordEditorMount");if(!list||!mount)return;
  if(!view.authenticated){list.innerHTML="";mount.innerHTML="";return;}
  const records=[...(view.records||[])].sort((a,b)=>b.date.localeCompare(a.date)||String(b.created_at||"").localeCompare(String(a.created_at||"")));
  list.innerHTML=records.length?records.map((record)=>`<article class="diary-admin-row"><div class="diary-admin-summary"><strong>${escapeHtml(record.title)}</strong><span>${escapeHtml(record.date)}${record.age_label?` · 🎂 ${escapeHtml(record.age_label)}`:""}</span><small>${escapeHtml(record.story)}</small><span class="diary-admin-attachments">${record.media?.length?`📷 ${record.media.length} 项附件`:"暂无附件"}</span></div><div class="diary-admin-actions"><button type="button" class="edit" data-admin-edit="${escapeHtml(record.id)}">编辑</button><button type="button" class="delete" data-admin-delete="${escapeHtml(record.id)}">删除</button></div></article>`).join(""):"<p class=\"diary-admin-empty\">还没有成长记录，点上方按钮添加第一条小故事吧 🌷</p>";
  list.querySelectorAll("[data-admin-edit]").forEach((button)=>button.addEventListener("click",()=>openDiaryRecordEditor(button.dataset.adminEdit)));
  list.querySelectorAll("[data-admin-delete]").forEach((button)=>button.addEventListener("click",()=>deleteRecord(button.dataset.adminDelete)));
  $("#addDiaryRecord").onclick=()=>openDiaryRecordEditor();
  mount.innerHTML=diaryEditorOpen?diaryRecordFormMarkup((view.records||[]).find((item)=>item.id===editingRecordId)||null):"";
  if(diaryEditorOpen){
    $("#recordForm").addEventListener("submit",saveRecord);
    $("#recordMediaInput").addEventListener("change",(event)=>uploadRecordFiles(event.currentTarget));
    $("#cancelEdit").addEventListener("click",()=>{diaryEditorOpen=false;editingRecordId=null;recordMedia=[];renderDiaryAdmin();});
    renderRecordMediaEditor();
  }
}
function openDiaryRecordEditor(id=null){
  editingRecordId=id;diaryEditorOpen=true;
  const record=(view.records||[]).find((item)=>item.id===id);
  recordMedia=(record?.media||[]).map((asset)=>({...asset}));
  setAdminTab("diary");renderDiaryAdmin();
  $("#recordForm")?.scrollIntoView({behavior:"smooth",block:"nearest"});
}
async function deleteRecord(id){
  if(!confirm("确定删除这条成长记录及它关联的照片和视频吗？删除后无法恢复，请先确认已有备份。"))return;
  try{await api(`/api/records/${encodeURIComponent(id)}`,{method:"DELETE",body:"{}"});view=await api("/api/state",{headers:{}});diaryEditorOpen=false;editingRecordId=null;recordMedia=[];render();setAdminTab("diary");}catch(error){alert(error.message);}
}
const scalarGroups=[
  {title:"网站名称和欢迎区",keys:["siteName","logoEmoji","navDiary","navLikes","heroBadge","heroLine1","heroLine2","heroLine3","heroEmoji","heroMascot","heroDescription","heroButton","float1","float2","float3"]},
  {title:"兴趣角标题",keys:["likesEyebrow","likesTitle","likesDescription"]},
  {title:"成长日记和页脚",keys:["diaryEyebrow","diaryTitle","diaryDescription","diaryCardEyebrow","diaryIcon","diaryCardTitle","diaryCardDescription","loginCta","recordFormTitle","recordDateLabel","recordTitleLabel","recordStoryLabel","recordTitlePlaceholder","recordStoryPlaceholder","recordSaveButton","recordCancelButton","emptyRecords","footerLeft","footerRight"]}
];
const fieldNames={siteName:"网站名称",logoEmoji:"网站标志图标",navDiary:"日记导航文字",navLikes:"兴趣导航文字",heroBadge:"欢迎区小标签",heroLine1:"欢迎标题第一行",heroLine2:"欢迎标题第二行",heroLine3:"欢迎标题第三行",heroEmoji:"标题旁边的表情",heroMascot:"插画主角表情",heroDescription:"欢迎区介绍",heroButton:"欢迎区按钮文字",float1:"插画气泡一",float2:"插画气泡二",float3:"插画气泡三",likesEyebrow:"兴趣角英文小标题",likesTitle:"兴趣角标题",likesDescription:"兴趣角介绍",diaryEyebrow:"日记区英文小标题",diaryTitle:"日记区标题",diaryDescription:"日记区介绍",diaryCardEyebrow:"日记卡片小标题",diaryIcon:"日记卡片图标",diaryCardTitle:"日记卡片标题",diaryCardDescription:"日记卡片说明",loginCta:"家长登录按钮文字",recordFormTitle:"记录表单标题",recordDateLabel:"日期字段名称",recordTitleLabel:"记录标题字段名称",recordStoryLabel:"故事字段名称",recordTitlePlaceholder:"记录标题提示语",recordStoryPlaceholder:"故事输入提示语",recordSaveButton:"保存按钮文字",recordCancelButton:"取消修改按钮文字",emptyRecords:"无记录时提示语",footerLeft:"页脚左侧文字",footerRight:"页脚右侧文字"};
function inputField(key,value,large=false){return `<label class="editor-field ${large?"wide-field":""}">${escapeHtml(fieldNames[key]||key)}${large?`<textarea data-content-key="${escapeHtml(key)}" maxlength="800">${escapeHtml(value)}</textarea>`:`<input data-content-key="${escapeHtml(key)}" value="${escapeHtml(value)}" maxlength="500">`}</label>`;}
function mascotEditorField(value){const image=/^\/media\/[a-f0-9]{32}\.(?:jpg|jpeg|png|webp|gif)$/.test(String(value||""));return `<div class="mascot-editor"><label class="editor-field">主视觉角色表情<input data-mascot-emoji value="${image?"":escapeHtml(value||"🐻")}" maxlength="16" placeholder="输入表情，例如 🐻"></label><input type="hidden" data-content-key="heroMascot" data-mascot-value value="${escapeHtml(value||"🐻")}"><div class="mascot-preview" id="mascotPreview">${image?`<img src="${escapeHtml(value)}" alt="当前主视觉角色">`:escapeHtml(value||"🐻")}</div><label class="upload-label">上传头像或 GIF<input id="uploadMascot" type="file" accept="image/jpeg,image/png,image/webp,image/gif,image/heic,image/heif"></label><button type="button" class="mascot-reset" id="resetMascot">改回表情</button><small id="mascotUploadStatus">静态照片自动压缩为 WebP，GIF 保留动画。</small></div>`;}
function renderContentEditor(){
  const c=view.content||CONTENT_DEFAULTS;let html="";
  for(const group of scalarGroups){html+=`<fieldset class="editor-group"><legend>${escapeHtml(group.title)}</legend><div class="editor-grid">${group.keys.map((key)=>key==="heroMascot"?mascotEditorField(c[key]):inputField(key,c[key],["heroDescription","likesDescription","diaryDescription","diaryCardDescription"].includes(key))).join("")}</div></fieldset>`;}
  html+=`<fieldset class="editor-group"><legend>首页基本介绍</legend><p class="editor-hint">三张简短介绍卡片，会显示在欢迎区下方。</p><div class="editor-cards">${c.profile.map((item,index)=>`<div class="editor-card"><strong>介绍卡片 ${index+1}</strong><label>图标<input data-profile-index="${index}" data-profile-key="icon" maxlength="16" value="${escapeHtml(item.icon)}"></label><label>标题<input data-profile-index="${index}" data-profile-key="title" maxlength="50" value="${escapeHtml(item.title)}"></label><label>说明<input data-profile-index="${index}" data-profile-key="text" maxlength="100" value="${escapeHtml(item.text)}"></label></div>`).join("")}</div></fieldset>`;
  html+=`<fieldset class="editor-group"><legend>兴趣卡片</legend><p class="editor-hint">每张卡片最多添加 50 个图片、视频、音频、网易云外链或在线曲目；单个文件最多 200 MB。兴趣卡片媒体对访客公开显示。</p><div id="interestEditorList" class="editor-cards">${c.interests.map((item,index)=>interestEditorCard(item,index)).join("")}</div><button type="button" class="add-interest" id="addInterest">＋ 添加兴趣卡片</button></fieldset>`;
  $("#contentEditor").innerHTML=html;
  $("#uploadMascot").addEventListener("change",uploadMascot);
  $("#resetMascot").addEventListener("click",()=>{const field=$("[data-mascot-value]"),emoji=$("[data-mascot-emoji]"),preview=$("#mascotPreview");field.value="🐻";emoji.value="🐻";preview.textContent="🐻";$("#mascotUploadStatus").textContent="已改回默认小熊；保存首页内容后生效。";});
  $("[data-mascot-emoji]").addEventListener("input",(event)=>{const value=event.currentTarget.value.trim();$("[data-mascot-value]").value=value;$("#mascotPreview").textContent=value||"🐻";});
  $("#addInterest").addEventListener("click",()=>{const list=$("#interestEditorList");if(list.children.length>=8)return;list.insertAdjacentHTML("beforeend",interestEditorCard({icon:"✨",title:"新兴趣",description:"写一写她喜欢做的事情。",tag:"小小发现",media:[]},list.children.length));bindInterestEditor();});
  bindInterestEditor();
}
function interestEditorCard(item,index){const media=Array.isArray(item.media)?item.media:[];return `<div class="editor-card interest-editor-card"><div class="editor-card-heading"><strong>兴趣 ${index+1}</strong><button type="button" class="delete" data-remove-interest>删除卡片</button></div><label>图标<input data-interest-index="${index}" data-interest-key="icon" maxlength="16" value="${escapeHtml(item.icon)}"></label><label>标题<input data-interest-index="${index}" data-interest-key="title" maxlength="80" value="${escapeHtml(item.title)}"></label><label>说明<textarea data-interest-index="${index}" data-interest-key="description" maxlength="240">${escapeHtml(item.description)}</textarea></label><label>小标签<input data-interest-index="${index}" data-interest-key="tag" maxlength="60" value="${escapeHtml(item.tag)}"></label><div class="media-manager"><strong>作品、照片、视频和音频</strong><label class="upload-label">选择并上传文件<input type="file" data-upload-interest multiple accept="image/jpeg,image/png,image/webp,image/gif,image/heic,image/heif,video/mp4,video/webm,video/quicktime,audio/mpeg,audio/mp4,audio/aac,audio/ogg,audio/wav"></label><span class="upload-status" data-upload-status></span><div class="music-search"><input data-music-query placeholder="搜索歌曲或故事名称"><select data-music-kind aria-label="内容类型"><option value="song">歌曲</option><option value="album">故事 / 专辑</option></select><button type="button" data-search-music>搜索在线内容</button></div><div class="music-search-results" data-music-results></div><div class="media-editor-list">${media.map(mediaEditorRow).join("")}</div><div class="netease-add"><input data-netease-title placeholder="故事专辑名称"><input data-netease-url placeholder="网易云分享链接（music.163.com）"><button type="button" data-add-netease>添加网易云外链</button></div><small>静态照片自动转 WebP；网易云外链仍会跳转到官方页面。在线搜索播放需先在“音乐音源”配置兼容 API。</small></div></div>`;}
function mediaEditorRow(asset){const track=asset.type==="provider-track"?JSON.stringify(asset.track||{}):"";return `<div class="media-editor-row" data-media-type="${escapeHtml(asset.type)}" data-media-url="${escapeHtml(asset.url||"")}" data-media-name="${escapeHtml(asset.name||"")}" data-saved-item-key="${escapeHtml(asset.savedItemKey||"")}" data-track="${escapeHtml(track)}"><span class="media-type-icon">${asset.type==="image"?"🖼️":asset.type==="video"?"🎬":asset.type==="audio"?"🎵":"🎧"}</span><input data-media-title maxlength="120" aria-label="作品名称" value="${escapeHtml(asset.title||asset.name||asset.track?.title||"")}"><button type="button" class="delete" data-remove-media aria-label="移除此内容">移除</button></div>`;}
function bindInterestEditor(){
  const list=$("#interestEditorList");
  list.querySelectorAll("[data-remove-interest]").forEach((button)=>button.onclick=()=>{if(list.children.length<=1)return;button.closest(".interest-editor-card").remove();renumberInterestEditor();});
  list.querySelectorAll("[data-remove-media]").forEach((button)=>button.onclick=()=>button.closest(".media-editor-row").remove());
  list.querySelectorAll("[data-upload-interest]").forEach((input)=>input.onchange=()=>uploadInterestFiles(input));
  list.querySelectorAll("[data-add-netease]").forEach((button)=>button.onclick=()=>addNeteaseLink(button));
  list.querySelectorAll("[data-search-music]").forEach((button)=>button.onclick=()=>searchMusicForCard(button));
  list.querySelectorAll("[data-add-provider-track]").forEach((button)=>button.onclick=()=>addProviderTrack(button));
}
async function searchMusicForCard(button){
  const card=button.closest(".interest-editor-card"),query=card.querySelector("[data-music-query]").value.trim(),kind=card.querySelector("[data-music-kind]").value,results=card.querySelector("[data-music-results]"),status=card.querySelector("[data-upload-status]");
  if(!query){status.textContent="请先输入歌曲或故事名称。";return;}button.disabled=true;results.innerHTML="";status.textContent="正在搜索已配置音源…";
  try{const data=await api(`/api/music/search?q=${encodeURIComponent(query)}&kind=${encodeURIComponent(kind)}`,{headers:{}});results.innerHTML=data.results.map((track)=>`<div class="music-result">${track.coverUrl?`<img src="${escapeHtml(track.coverUrl)}" alt="" loading="lazy">`:"<span>🎧</span>"}<div><strong>${escapeHtml(track.title)}</strong><small>${escapeHtml([track.creator,track.collection,track.providerName].filter(Boolean).join(" · "))}</small></div><button type="button" data-add-provider-track data-track="${escapeHtml(JSON.stringify(track))}">添加</button></div>`).join("")||"<p>没有找到结果；可以换个关键词，或继续使用本地上传音频。</p>";if(data.errors.length)status.textContent=data.errors.map((item)=>`${item.providerName}：${item.message}`).join(" ");else status.textContent="";bindInterestEditor();}
  catch(error){status.textContent=error.message;}
  finally{button.disabled=false;}
}
function addProviderTrack(button){
  const track=JSON.parse(button.dataset.track||"{}");if(!track.providerId||!track.itemId)return;
  const asset={type:"provider-track",title:track.title,name:track.providerName,savedItemKey:newUploadId(),track};
  button.closest(".interest-editor-card").querySelector(".media-editor-list").insertAdjacentHTML("beforeend",mediaEditorRow(asset));button.closest(".music-result").remove();bindInterestEditor();
}
async function uploadInterestFiles(input){
  const card=input.closest(".interest-editor-card"),status=card.querySelector("[data-upload-status]"),files=Array.from(input.files||[]);input.disabled=true;
  try{for(const file of files){const data=await uploadMediaFile(file,(message)=>{status.textContent=`${file.name}：${message}`;});card.querySelector(".media-editor-list").insertAdjacentHTML("beforeend",mediaEditorRow(data));}status.textContent=files.length?`已上传 ${files.length} 个文件，保存首页内容后生效。`:"";bindInterestEditor();}
  catch(error){status.textContent=error.message;}
  finally{input.disabled=false;input.value="";}
}
async function uploadMascot(event){
  const input=event.currentTarget,file=input.files?.[0];if(!file)return;
  const status=$("#mascotUploadStatus");input.disabled=true;status.textContent=`正在上传 ${file.name}…`;
  try{const data=await uploadMediaFile(file,(message)=>{status.textContent=`${file.name}：${message}`;});if(data.type!=="image")throw new Error("请选择图片或 GIF 文件。");$("[data-mascot-value]").value=data.url;$("[data-mascot-emoji]").value="";const image=document.createElement("img");image.src=data.url;image.alt="主视觉角色预览";$("#mascotPreview").replaceChildren(image);status.textContent="已上传；保存首页内容后生效。";}
  catch(error){status.textContent=error.message;}
  finally{input.disabled=false;input.value="";}
}
function addNeteaseLink(button){
  const card=button.closest(".interest-editor-card"),titleInput=card.querySelector("[data-netease-title]"),urlInput=card.querySelector("[data-netease-url]"),title=titleInput.value.trim(),url=urlInput.value.trim();
  try{const parsed=new URL(url);if(parsed.protocol!=="https:"||!(["music.163.com","www.music.163.com"].includes(parsed.hostname))||!title)throw new Error();card.querySelector(".media-editor-list").insertAdjacentHTML("beforeend",mediaEditorRow({type:"netease",title,name:"网易云音乐",url}));titleInput.value="";urlInput.value="";bindInterestEditor();}
  catch{card.querySelector("[data-upload-status]").textContent="请填写名称和 music.163.com 的 HTTPS 分享链接。";}
}
function renumberInterestEditor(){
  $("#interestEditorList").querySelectorAll(".interest-editor-card").forEach((card,index)=>{card.querySelector("strong").textContent=`兴趣 ${index+1}`;card.querySelectorAll("[data-interest-key]").forEach((field)=>field.dataset.interestIndex=index);});
}
function collectContent(){
  const c={};for(const field of $("#contentEditor").querySelectorAll("[data-content-key]"))c[field.dataset.contentKey]=field.value.trim();
  c.profile=Array.from({length:3},(_,index)=>{const row={};$("#contentEditor").querySelectorAll(`[data-profile-index="${index}"]`).forEach((field)=>row[field.dataset.profileKey]=field.value.trim());return row;});
  c.interests=Array.from($("#interestEditorList").querySelectorAll(".interest-editor-card"),(card)=>{const item={};card.querySelectorAll("[data-interest-key]").forEach((field)=>item[field.dataset.interestKey]=field.value.trim());item.media=Array.from(card.querySelectorAll(".media-editor-row"),(row)=>{const asset={type:row.dataset.mediaType,title:row.querySelector("[data-media-title]").value.trim(),name:row.dataset.mediaName,url:row.dataset.mediaUrl};if(asset.type==="provider-track"){asset.savedItemKey=row.dataset.savedItemKey;asset.track=JSON.parse(row.dataset.track||"{}");delete asset.url;}return asset;});return item;});
  return c;
}
function musicSourceRow(source={}){return `<div class="music-source-row" data-source-id="${escapeHtml(source.id||newUploadId())}"><label>显示名称<input data-source-name maxlength="80" value="${escapeHtml(source.name||"")}" placeholder="例如：家庭音乐 API"></label><label>API 地址<input data-source-url type="url" value="${escapeHtml(source.baseUrl||"")}" placeholder="https://你的服务地址/api.php"></label><label>平台代码<input data-source-platform maxlength="40" value="${escapeHtml(source.platform||"netease")}" placeholder="netease / tencent / kugou"></label><label>服务密钥（可选）<input data-source-key type="password" autocomplete="new-password" placeholder="${source.hasKey?"已保存；留空保持不变":"如服务需要，请填写"}"></label><label class="source-enabled"><input data-source-enabled type="checkbox" ${source.enabled===false?"":"checked"}>启用</label><button type="button" class="delete" data-remove-source>删除音源</button><button type="button" class="backup-button" data-test-source>测试连接</button><span class="source-test-status" role="status"></span></div>`;}
async function renderMusicAdmin(){
  const list=$("#musicSourceList"),status=$("#musicAdminStatus");if(!list)return;
  try{const data=await api("/api/music/config",{headers:{}});musicSources=data.sources||[];list.innerHTML=musicSources.map(musicSourceRow).join("")||"<p class=\"editor-hint\">还没有配置音源。点击“添加音源”开始。</p>";bindMusicSourceEditor();status.textContent="";}
  catch(error){status.textContent=error.message;}
}
function bindMusicSourceEditor(){
  $("#musicSourceList").querySelectorAll("[data-remove-source]").forEach((button)=>button.onclick=()=>button.closest(".music-source-row").remove());
  $("#musicSourceList").querySelectorAll("[data-test-source]").forEach((button)=>button.onclick=async()=>{const row=button.closest(".music-source-row"),status=row.querySelector(".source-test-status"),source=musicSourceFromRow(row);button.disabled=true;status.textContent="正在测试…";try{const result=await api("/api/music/test",{method:"POST",body:JSON.stringify({source})});status.textContent=result.message;}catch(error){status.textContent=error.message;}finally{button.disabled=false;}});
}
function musicSourceFromRow(row){return {id:row.dataset.sourceId,name:row.querySelector("[data-source-name]").value.trim(),baseUrl:row.querySelector("[data-source-url]").value.trim(),platform:row.querySelector("[data-source-platform]").value.trim(),apiKey:row.querySelector("[data-source-key]").value,enabled:row.querySelector("[data-source-enabled]").checked};}
$("#addMusicSource").addEventListener("click",()=>{$("#musicSourceList").insertAdjacentHTML("beforeend",musicSourceRow());bindMusicSourceEditor();});
$("#saveMusicSources").addEventListener("click",async()=>{const button=$("#saveMusicSources"),status=$("#musicAdminStatus");button.disabled=true;status.textContent="正在保存…";try{const sources=Array.from($("#musicSourceList").querySelectorAll(".music-source-row"),musicSourceFromRow);await api("/api/music/config",{method:"PUT",body:JSON.stringify({sources})});status.textContent="音源设置已保存。";await renderMusicAdmin();}catch(error){status.textContent=error.message;}finally{button.disabled=false;}});
$("#contentButton").addEventListener("click",()=>{renderContentEditor();renderDiaryAdmin();renderMusicAdmin();setAdminTab("content");$("#contentStatus").textContent="";contentDialog.showModal();});
document.querySelectorAll("[data-admin-tab]").forEach((button)=>button.addEventListener("click",()=>{setAdminTab(button.dataset.adminTab);if(button.dataset.adminTab==="music")renderMusicAdmin();}));
contentDialog.addEventListener("close",()=>{if(diaryEditorOpen){diaryEditorOpen=false;editingRecordId=null;recordMedia=[];renderDiaryAdmin();}});
$("#contentForm").addEventListener("submit",async(event)=>{
  event.preventDefault();if($("#contentEditor input[type=file]:disabled")){ $("#contentStatus").textContent="请等文件上传完成后再保存。";return;}const button=event.currentTarget.querySelector("button[type=submit]");button.disabled=true;$("#contentStatus").textContent="正在保存…";
  try{const result=await api("/api/content",{method:"PUT",body:JSON.stringify(collectContent())});view.content=result.content;applyContent(view.content);contentDialog.close();}
  catch(error){$("#contentStatus").textContent=error.message;}
  finally{button.disabled=false;}
});
authForm.addEventListener("submit",async(event)=>{
  event.preventDefault();const data=Object.fromEntries(new FormData(authForm).entries());const isSetup=view.setupRequired;
  try{await api(isSetup?"/api/setup":"/api/login",{method:"POST",body:JSON.stringify(data)});view=await api("/api/state",{headers:{}});authDialog.close();authForm.reset();render();}
  catch(error){$("#authError").textContent=error.message;}
});
$("#accountButton").addEventListener("click",async()=>{
  if(!view.authenticated)return openAuth();
  try{await api("/api/logout",{method:"POST",body:"{}"});view=await api("/api/state",{headers:{}});render();}catch(error){alert(error.message);}
});
$("#restoreBackupInput").addEventListener("change",async(event)=>{
  const input=event.currentTarget,file=input.files?.[0];if(!file)return;
  if(!confirm(`将使用“${file.name}”覆盖当前成长日记、网站设置和兴趣媒体。家长账号密码不会改变。继续恢复吗？`)){input.value="";return;}
  const status=$("#contentStatus");status.textContent="正在恢复备份…";input.disabled=true;
  try{const response=await fetch("/api/restore",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/gzip"},body:file});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error||"恢复失败，请检查备份文件。");view.records=data.records||[];view.content=data.content;contentDialog.close();render();alert("备份已恢复。");}
  catch(error){status.textContent=error.message;}
  finally{input.disabled=false;input.value="";}
});
$("#chooseRestoreBackup").addEventListener("click",()=>$("#restoreBackupInput").click());
$("#lightboxClose").addEventListener("click",()=>$("#diaryLightbox").close());
$("#lightboxPrevious").addEventListener("click",()=>{lightboxIndex--;updateDiaryLightbox();});
$("#lightboxNext").addEventListener("click",()=>{lightboxIndex++;updateDiaryLightbox();});
$("#diaryLightbox").addEventListener("click",(event)=>{if(event.target===event.currentTarget)event.currentTarget.close();});
$("#diaryLightbox").addEventListener("close",()=>{$("#lightboxStage").replaceChildren();lightboxRecordId=null;});
window.addEventListener("keydown",(event)=>{
  const dialog=$("#diaryLightbox");if(!dialog.open)return;
  if(event.key==="ArrowLeft"&&!$("#lightboxPrevious").disabled){event.preventDefault();lightboxIndex--;updateDiaryLightbox();}
  if(event.key==="ArrowRight"&&!$("#lightboxNext").disabled){event.preventDefault();lightboxIndex++;updateDiaryLightbox();}
});
const backToTop=$("#backToTop");
window.addEventListener("scroll",()=>backToTop.classList.toggle("visible",window.scrollY>420),{passive:true});
backToTop.addEventListener("click",()=>window.scrollTo({top:0,behavior:"smooth"}));
loadState();
