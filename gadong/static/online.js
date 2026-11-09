/* 원본은 저장소로 직접 전송하고, 계산 요청은 한 단계씩 기다린다. */
(() => {
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  async function post(url, data) {
    const response = await fetch(url, {method: 'POST', body: data, credentials: 'same-origin'});
    if (response.redirected && new URL(response.url).pathname === '/login') {
      const error = new Error('로그인 시간이 만료되었습니다. 새로 로그인해 주세요.'); error.status = 401; throw error;
    }
    const result = await response.json().catch(() => ({}));
    if (!response.ok) { const error = new Error(result.error || '요청을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.'); error.status = response.status; throw error; }
    return result;
  }
  const form = document.querySelector('[data-online-upload]');
  if (form) form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = document.getElementById('upbtn'), message = document.getElementById('upmsg');
    const file = form.querySelector('input[type=file]').files[0];
    try {
      if (!file || file.size > 20 * 1024 * 1024 || !file.size) throw new Error('20MB 이하의 엑셀 파일을 선택해 주세요.');
      const data = new FormData(form); data.delete('file'); data.set('name', file.name); data.set('size', file.size);
      button.disabled = true; message.textContent = '파일을 올리고 있습니다…';
      const signed = await post(form.dataset.onlineUpload, data);
      const uploaded = await fetch(signed.url, {method: 'PUT', headers: {'Content-Type': file.type || 'application/octet-stream'}, body: file});
      if (!uploaded.ok) throw new Error('파일 전송에 실패했습니다. 파일을 다시 올려 주세요.');
      message.textContent = '파일 양식과 반영 위치를 확인하고 있습니다…';
      const finish = new FormData(); finish.set('csrf', data.get('csrf')); finish.set('ticket', signed.ticket);
      let result;
      // 응답이 끊겨도 같은 접수 번호로 재시도하므로 중복 등록하지 않는다.
      for (let attempt = 0; attempt < 60; attempt++) {
        try { result = await post(form.dataset.finish, finish); break; }
        catch (error) { if (attempt === 59 || (error.status && error.status !== 409 && error.status !== 503)) throw error; await pause(10000); }
      }
      location.assign(result.url);
    } catch (error) {
      message.textContent = error.message; message.setAttribute('role', 'alert');
      button.disabled = false; button.textContent = '다시 업로드';
    }
  });
  document.querySelectorAll('[data-preview-run]').forEach(async element => {
    const data = new FormData(); data.set('csrf', element.dataset.csrf);
    try {
      const result = await post(element.dataset.previewRun, data);
      if (result.finished) location.reload();
      else { element.textContent = '다른 요청에서 미리보기를 만들고 있습니다. 잠시 후 다시 확인해 주세요.'; setTimeout(() => location.reload(), 5000); }
    } catch (error) { element.textContent = error.message; }
  });
  document.querySelectorAll('[data-job-run]').forEach(async element => {
    const data = new FormData(); data.set('csrf', element.dataset.csrf);
    while (document.contains(element)) {
      try {
        const result = await post(element.dataset.jobRun, data);
        if (!result.state || result.state !== 'running') { location.reload(); return; }
        element.textContent = `${result.cursor}/${result.total} 단계 완료 · ${result.step}${result.busy ? ' (계산 중)' : ''}`;
        await pause(result.busy ? 4000 : 300);
      } catch (error) {
        if (error.status === 401) { location.assign('/login'); return; }
        element.textContent = `${error.message} 연결되면 저장된 단계부터 이어집니다.`;
        await pause(5000);
      }
    }
  });
})();
