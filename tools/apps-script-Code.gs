/**
 * Plan-Follow · ส่งรายงาน E-REPORT จาก Gmail ขึ้นแอป MOC อัตโนมัติ
 *
 * ทุกเช้าสคริปต์นี้จะ:
 *   1. หาอีเมล "E-REPORT" ที่มีไฟล์ Fyp_Submission_Paid...pdf ซึ่งยังไม่เคยส่ง
 *   2. เข้ารหัสไฟล์ด้วยรหัสผ่านแอป แล้วอัปโหลดขึ้น GitHub (โฟลเดอร์ inbox/)
 *   3. ติดป้าย "plan-follow-done" ที่อีเมล เพื่อไม่ให้ส่งซ้ำ
 * จากนั้น GitHub จะอ่านตัวเลข อัปเดตแท็บ "เดือนนี้" และเข้ารหัสหน้าแอปใหม่เอง
 *
 * ตั้งค่าครั้งแรก: ใส่ Script properties 2 ค่า (GITHUB_TOKEN, APP_PASSWORD) แล้วกด Run ฟังก์ชัน setup
 */

const CONFIG = {
  REPO: 'sippanonkonjing-a11y/Plan-Follow',
  BRANCH: 'main',
  SEARCH: 'subject:E-REPORT has:attachment filename:pdf newer_than:7d -label:plan-follow-done',
  FILE_PATTERN: /Fyp_Submission_Paid.*\.pdf$/i,
  LABEL: 'plan-follow-done',
  HOUR: 7 // ทำงานทุกวันช่วง 7:00–8:00 น. (ตามเขตเวลาของโปรเจกต์)
};

/** กด Run ฟังก์ชันนี้ครั้งเดียวตอนตั้งค่า: ตรวจค่า ตั้งเวลาทำงานรายวัน และลองส่งรอบแรก */
function setup() {
  const p = PropertiesService.getScriptProperties();
  if (!p.getProperty('GITHUB_TOKEN') || !p.getProperty('APP_PASSWORD')) {
    throw new Error('ยังไม่ได้ใส่ GITHUB_TOKEN หรือ APP_PASSWORD ใน Project Settings → Script properties');
  }
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'run')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('run').timeBased().everyDays(1).atHour(CONFIG.HOUR).create();
  console.log('ตั้งเวลาทำงานทุกวันช่วง ' + CONFIG.HOUR + ':00 น. แล้ว');
  run();
}

/** ทำงานรายวัน: หาอีเมลใหม่ เข้ารหัสไฟล์ และอัปโหลด */
function run() {
  const p = PropertiesService.getScriptProperties();
  const token = p.getProperty('GITHUB_TOKEN');
  const password = p.getProperty('APP_PASSWORD');
  const label = GmailApp.getUserLabelByName(CONFIG.LABEL) || GmailApp.createLabel(CONFIG.LABEL);
  const threads = GmailApp.search(CONFIG.SEARCH, 0, 20);
  let uploaded = 0;
  threads.forEach(thread => {
    let ok = true;
    thread.getMessages().forEach(msg => {
      msg.getAttachments().forEach(att => {
        const name = att.getName();
        if (!CONFIG.FILE_PATTERN.test(name)) return;
        try {
          const blob = encryptPF1(att.getBytes(), password);
          putFile(token, 'inbox/' + name + '.bin', blob, 'E-REPORT ' + name);
          uploaded++;
          console.log('ส่งแล้ว: ' + name);
        } catch (e) {
          ok = false;
          console.error('ส่งไม่สำเร็จ: ' + name + ' · ' + e.message);
        }
      });
    });
    if (ok) thread.addLabel(label);
  });
  console.log(uploaded ? 'ส่งรายงานทั้งหมด ' + uploaded + ' ไฟล์' : 'ไม่มีรายงานใหม่');
}

/* ---------- เข้ารหัส (ต้องตรงกับ tools/pfcrypt.py ใน GitHub) ---------- */

function encryptPF1(data, password) {
  const key = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, 'plan-follow-inbox:' + password, Utilities.Charset.UTF_8);
  const nonce = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, Utilities.getUuid() + Date.now(), Utilities.Charset.UTF_8).slice(0, 16);
  const ct = new Array(data.length);
  let block = [], counter = 0;
  for (let i = 0; i < data.length; i++) {
    const j = i % 32;
    if (j === 0) {
      block = Utilities.computeHmacSha256Signature(nonce.concat(be32(counter)), key);
      counter++;
    }
    ct[i] = data[i] ^ block[j];
  }
  const tag = Utilities.computeHmacSha256Signature([116, 97, 103].concat(nonce, ct), key);
  return [80, 70, 49].concat(nonce, ct, tag);
}

function be32(n) {
  return [(n >>> 24) & 255, (n >>> 16) & 255, (n >>> 8) & 255, n & 255].map(b => (b << 24) >> 24);
}

/* ---------- อัปโหลดขึ้น GitHub ---------- */

function putFile(token, path, bytes, message) {
  const url = 'https://api.github.com/repos/' + CONFIG.REPO + '/contents/' + path.split('/').map(encodeURIComponent).join('/');
  const headers = { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' };
  const body = { message: message, content: Utilities.base64Encode(bytes), branch: CONFIG.BRANCH };
  const existing = UrlFetchApp.fetch(url + '?ref=' + CONFIG.BRANCH, { headers: headers, muteHttpExceptions: true });
  if (existing.getResponseCode() === 200) body.sha = JSON.parse(existing.getContentText()).sha;
  const res = UrlFetchApp.fetch(url, { method: 'put', headers: headers, contentType: 'application/json', payload: JSON.stringify(body), muteHttpExceptions: true });
  const code = res.getResponseCode();
  if (code !== 200 && code !== 201) {
    const hint = code === 401 ? ' (GITHUB_TOKEN ไม่ถูกต้องหรือหมดอายุ)' : code === 403 || code === 404 ? ' (GITHUB_TOKEN ยังไม่ได้สิทธิ์ Contents: Read and write ของ Plan-Follow)' : '';
    throw new Error('GitHub ตอบกลับ ' + code + hint + ': ' + res.getContentText().slice(0, 200));
  }
}
