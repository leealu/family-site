// Run with NODE_PATH pointing to a Playwright installation and PYTHON to Python 3.
// Uses generated images and disposable data; never reads personal media.
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {mkdtempSync, rmSync} = require('node:fs');
const {tmpdir} = require('node:os');
const path = require('node:path');
const {chromium} = require('playwright');
(async () => {
  const data = mkdtempSync(path.join(tmpdir(), 'family-image-test-'));
  const port = 18746;
  const server = spawn(process.env.PYTHON || 'python', ['outputs/site/server.py'], {
    cwd: path.resolve(__dirname, '..'),
    env: {...process.env, DIARY_DATA_DIR:data, PORT:String(port)}, stdio:'ignore'
  });
  let browser;
  try {
    browser = await chromium.launch({channel:'chrome', headless:true});
    const page = await browser.newPage();
    for (let attempt=0; ; attempt++) {
      try { await page.goto(`http://127.0.0.1:${port}`); break; }
      catch(error) { if(attempt>=40) throw error; await new Promise(r=>setTimeout(r,100)); }
    }
    // Hold the real state response to reproduce a slow refresh without personal data.
    let releaseState;
    let stateRequested;
    const requested = new Promise(resolve => { stateRequested=resolve; });
    const gate = new Promise(resolve => { releaseState=resolve; });
    const avatar='/media/11111111111111111111111111111111.png';
    await page.route('**/api/state', async route => {
      const response=await route.fetch();
      const state=await response.json();
      state.content.heroMascot=avatar;
      stateRequested();
      await gate;
      await route.fulfill({response,json:state});
    });
    await page.reload({waitUntil:'domcontentloaded'});
    await requested;
    try {
      assert.equal(await page.locator('#heroMascot').innerText(), '',
        'Saved avatar must not flash a default bear while state is loading');
    } finally { releaseState(); }
    await page.waitForFunction(avatar=>document.querySelector('#heroMascot img')?.getAttribute('src')===avatar,avatar);
    assert.equal(await page.locator('#heroMascot').innerText(),'');
    console.log('PASS: slow refresh shows no default bear before saved avatar');
    await page.unroute('**/api/state');
    await page.reload();
    await page.waitForFunction(()=>document.querySelector('#heroMascot').textContent==='🐻');
    console.log('PASS: default bear appears when saved settings use it');
    const result = await page.evaluate(async () => {
      const canvas = document.createElement('canvas'); canvas.width=2400; canvas.height=1200;
      canvas.getContext('2d').fillRect(0,0,2400,1200);
      const png = await new Promise(r=>canvas.toBlob(r,'image/png'));
      const file = await prepareImageForUpload(new File([png],'fixture.png',{type:'image/png'}));
      const bitmap = await createImageBitmap(file);
      return {name:file.name,type:file.type,width:bitmap.width,height:bitmap.height,size:file.size};
    });
    assert.equal(result.name,'fixture.webp'); assert.equal(result.type,'image/webp');
    assert.equal(result.width,1920); assert.equal(result.height,960); assert.ok(result.size>0);
    console.log('PASS: valid PNG decodes under real server CSP and converts/resizes to WebP');
    const bad = await page.evaluate(async () => {
      try { await prepareImageForUpload(new File(['invalid'],'broken.png',{type:'image/png'})); return ''; }
      catch(error) { return error.message; }
    });
    assert.ok(bad); assert.ok(!bad.includes('iPhone'), 'PNG errors must not recommend iPhone settings');
    console.log('PASS: invalid PNG has a format-appropriate error');
    for(const type of ['image/webp','image/gif']) {
      assert.equal(await page.evaluate(async type=>{const file=new File(['fixture'],'fixture.'+type.split('/')[1],{type});return await prepareImageForUpload(file)===file;},type),true);
    }
    console.log('PASS: WebP and animated GIF passthrough preserved');
  } finally {
    if(browser) await browser.close(); server.kill();
    await new Promise(resolve=>server.exitCode!==null?resolve():server.once('exit',resolve));
    rmSync(data,{recursive:true,force:true});
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
