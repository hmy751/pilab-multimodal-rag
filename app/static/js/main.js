/* ============================================================
   MediaFlow AI Agent — 클라이언트 스크립트
   ============================================================ */

// ── 상태 ──
let selectedMediaId = null;
let evalQuestions = [];
let evalChart = null;

// ── DOM ──
const uploadArea    = document.getElementById('upload-area');
const fileInput     = document.getElementById('file-input');
const uploadBtn     = document.getElementById('upload-btn');
const uploadStatus  = document.getElementById('upload-status');
const progressBar   = document.getElementById('progress-bar');
const statusText    = document.getElementById('status-text');
const mediaList     = document.getElementById('media-list');
const refreshBtn    = document.getElementById('refresh-btn');
const audioPlayer   = document.getElementById('audio-player');
const videoPlayer   = document.getElementById('video-player');
const playerPlaceholder = document.getElementById('player-placeholder');
const transcriptList = document.getElementById('transcript-list');
const segmentCount  = document.getElementById('segment-count');
const questionInput = document.getElementById('question-input');
const evalIncludeCb = document.getElementById('eval-include-cb');
const askBtn        = document.getElementById('ask-btn');
const answerArea    = document.getElementById('answer-area');
const answerContent = document.getElementById('answer-content');
const sourcesList   = document.getElementById('sources-list');
const chatHistory   = document.getElementById('chat-history');
const evalQuestionCount = document.getElementById('eval-question-count');
const runEvalBtn    = document.getElementById('run-eval-btn');
const werReference  = document.getElementById('wer-reference');
const evalChartWrap = document.getElementById('eval-chart-wrap');
const evalResultRaw = document.getElementById('eval-result-raw');
const healthBadge   = document.getElementById('health-badge');
const summaryBtn    = document.getElementById('summary-btn');
const summaryContent = document.getElementById('summary-content');

// ────────────────────────────────────────
// 헬스 체크
// ────────────────────────────────────────
async function checkHealth() {
  try {
    const res = await fetch('/health');
    const data = await res.json();
    const ok = data.status === 'ok';
    healthBadge.textContent = ok ? '● 정상' : '● 오류';
    healthBadge.className = `badge ${ok ? 'badge-ok' : 'badge-error'}`;
  } catch {
    healthBadge.textContent = '● 연결 실패';
    healthBadge.className = 'badge badge-error';
  }
}
checkHealth();

// ────────────────────────────────────────
// 파일 업로드
// ────────────────────────────────────────
uploadBtn.addEventListener('click', () => fileInput.click());
uploadArea.addEventListener('click', (e) => { if (e.target === uploadArea) fileInput.click(); });
fileInput.addEventListener('change', () => { if (fileInput.files[0]) uploadFile(fileInput.files[0]); });

uploadArea.addEventListener('dragover', (e) => { e.preventDefault(); uploadArea.classList.add('drag-over'); });
uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('drag-over'));
uploadArea.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadArea.classList.remove('drag-over');
  if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]);
});

async function uploadFile(file) {
  uploadStatus.classList.remove('hidden');
  progressBar.style.width = '10%';
  statusText.textContent = '업로드 중…';

  const formData = new FormData();
  formData.append('file', file);

  let jobId, mediaId;
  try {
    const res = await fetch('/media/upload', { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || '업로드 실패');
    }
    const data = await res.json();
    jobId = data.job_id;
    mediaId = data.media_id;
    progressBar.style.width = '25%';
    statusText.textContent = `전사 대기 중… (job: ${jobId.slice(0, 8)})`;
  } catch (e) {
    statusText.textContent = `오류: ${e.message}`;
    progressBar.style.width = '0%';
    return;
  }

  // Job 폴링
  pollJob(jobId, mediaId);
}

async function pollJob(jobId, mediaId) {
  const POLL_INTERVAL_MS = 3000;
  const progressMap = {
    pending: 25,
    transcribing: 45,
    analyzing_frames: 65,
    embedding: 85,
    ready: 100,
    failed: 0,
  };
  const labelMap = {
    pending: '처리 대기 중…',
    transcribing: '전사 중… (CPU 성능에 따라 수 분 소요)',
    analyzing_frames: '프레임 분석 중…',
    embedding: '임베딩 및 저장 중…',
    ready: '처리 완료!',
    failed: '처리 실패',
  };

  while (true) {
    await sleep(POLL_INTERVAL_MS);
    try {
      const res = await fetch(`/media/jobs/${jobId}`);
      if (!res.ok) break;
      const job = await res.json();
      const pct = progressMap[job.status] ?? 30;
      progressBar.style.width = `${pct}%`;
      statusText.textContent = labelMap[job.status] ?? job.status;

      if (job.status === 'ready') {
        setTimeout(() => { uploadStatus.classList.add('hidden'); progressBar.style.width = '0%'; }, 2000);
        loadMediaList();
        return;
      }
      if (job.status === 'failed') {
        statusText.textContent = `처리 실패: ${job.error || '알 수 없는 오류'}`;
        progressBar.style.width = '0%';
        return;
      }
    } catch {
      break;
    }
  }
}

// ────────────────────────────────────────
// 미디어 목록
// ────────────────────────────────────────
refreshBtn.addEventListener('click', loadMediaList);
loadMediaList();

async function loadMediaList() {
  try {
    const res = await fetch('/media/');
    const data = await res.json();
    renderMediaList(data.media || []);
  } catch {
    mediaList.innerHTML = '<li class="media-item-empty">목록 로드 실패</li>';
  }
}

function renderMediaList(items) {
  if (!items.length) {
    mediaList.innerHTML = '<li class="media-item-empty">업로드된 파일이 없습니다.</li>';
    return;
  }
  mediaList.innerHTML = items.map(m => `
    <li class="media-item ${m.id === selectedMediaId ? 'active' : ''}" data-id="${m.id}" data-type="${m.file_type}">
      <div class="media-item-name">${escapeHtml(m.filename)}</div>
      <div class="media-item-meta">${m.file_type} · ${formatDuration(m.duration_seconds)} · ${m.segment_count ?? 0}개 세그먼트</div>
      <span class="media-item-status status-${m.status}">${m.status}</span>
    </li>
  `).join('');
  mediaList.querySelectorAll('.media-item').forEach(el => {
    el.addEventListener('click', () => selectMedia(el.dataset.id, el.dataset.type, el.querySelector('.media-item-name').textContent));
  });
}

function selectMedia(mediaId, fileType, filename) {
  selectedMediaId = mediaId;
  document.querySelectorAll('.media-item').forEach(el => el.classList.toggle('active', el.dataset.id === mediaId));
  loadTranscript(mediaId);
  summaryBtn.disabled = false;
  summaryContent.innerHTML = '<p class="empty-msg">요약 생성 버튼을 눌러주세요.</p>';

  // 플레이어 숨기기
  audioPlayer.classList.add('hidden');
  videoPlayer.classList.add('hidden');
  playerPlaceholder.classList.add('hidden');

  const mediaUrl = `/media/${mediaId}/file`;
  if (fileType === 'video') {
    videoPlayer.src = mediaUrl;
    videoPlayer.classList.remove('hidden');
  } else {
    audioPlayer.src = mediaUrl;
    audioPlayer.classList.remove('hidden');
  }
}

// ────────────────────────────────────────
// 전사 목록 로드
// ────────────────────────────────────────
async function loadTranscript(mediaId) {
  transcriptList.innerHTML = '<p class="empty-msg">로드 중…</p>';
  try {
    const res = await fetch(`/media/${mediaId}/segments`);
    if (!res.ok) throw new Error();
    const data = await res.json();
    renderTranscript(data.segments || []);
  } catch {
    transcriptList.innerHTML = '<p class="empty-msg">전사 데이터를 불러올 수 없습니다. supabase_utils를 구현하세요.</p>';
  }
}

function renderTranscript(segments) {
  segmentCount.textContent = `${segments.length}개`;
  if (!segments.length) {
    transcriptList.innerHTML = '<p class="empty-msg">세그먼트가 없습니다.</p>';
    return;
  }
  transcriptList.innerHTML = segments.map(seg => `
    <div class="segment-item ${seg.frame_description ? 'has-frame' : ''}">
      <div class="segment-timestamp">[${formatTime(seg.start_time)} – ${formatTime(seg.end_time)}]</div>
      <div class="segment-text">${escapeHtml(seg.text)}</div>
      ${seg.frame_description ? `<div class="segment-frame-desc">📷 ${escapeHtml(seg.frame_description)}</div>` : ''}
    </div>
  `).join('');
}

// ────────────────────────────────────────
// 요약
// ────────────────────────────────────────
summaryBtn.addEventListener('click', loadSummary);

async function loadSummary() {
  if (!selectedMediaId) return;
  summaryBtn.disabled = true;
  summaryBtn.textContent = '요약 생성 중…';
  summaryContent.innerHTML = '<p class="empty-msg">요약 생성 중…</p>';

  try {
    const res = await fetch(`/media/${selectedMediaId}/summary`, { method: 'POST' });
    if (!res.ok) throw new Error();
    const data = await res.json();
    summaryContent.innerHTML = `<div class="summary-text">${escapeHtml(data.summary)}</div>`;
  } catch {
    summaryContent.innerHTML = '<p class="empty-msg">요약 생성에 실패했습니다.</p>';
  } finally {
    summaryBtn.disabled = false;
    summaryBtn.textContent = '요약 생성';
  }
}

// ────────────────────────────────────────
// Q&A
// ────────────────────────────────────────
askBtn.addEventListener('click', askQuestion);
questionInput.addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) askQuestion(); });

async function askQuestion() {
  const question = questionInput.value.trim();
  if (!question) return;
  if (!selectedMediaId) { alert('왼쪽에서 미디어를 먼저 선택하세요.'); return; }

  if (evalIncludeCb.checked) {
    addEvalQuestion(question);
    evalIncludeCb.checked = false;
  }

  askBtn.disabled = true;
  askBtn.textContent = '답변 생성 중…';
  answerArea.classList.add('hidden');

  try {
    const res = await fetch('/qa', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: question, media_id: selectedMediaId }),
    });
    const data = await res.json();

    document.getElementById('question-content').textContent = `Q: ${question}`;
    answerContent.textContent = data.answer;
    sourcesList.innerHTML = (data.sources || []).map(s =>
      `<div class="source-item">[${formatTime(s.start_time)}–${formatTime(s.end_time)}] ${escapeHtml(s.text?.slice(0, 80))}…</div>`
    ).join('');
    answerArea.classList.remove('hidden');

    appendChatHistory(question, data.answer);
    questionInput.value = '';
  } catch (e) {
    answerContent.textContent = '오류가 발생했습니다. /qa 엔드포인트를 구현하세요.';
    answerArea.classList.remove('hidden');
  } finally {
    askBtn.disabled = false;
    askBtn.textContent = '질문하기';
  }
}

function appendChatHistory(q, a) {
  const div = document.createElement('div');
  div.innerHTML = `<div class="chat-q">Q: ${escapeHtml(q)}</div><div class="chat-a">${escapeHtml(a)}</div>`;
  chatHistory.appendChild(div);
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

// ────────────────────────────────────────
// 평가
// ────────────────────────────────────────
function addEvalQuestion(q) {
  if (!evalQuestions.includes(q)) {
    evalQuestions.push(q);
    updateEvalUI();
  }
}

function updateEvalUI() {
  evalQuestionCount.textContent = `포함된 질문: ${evalQuestions.length}개`;
  runEvalBtn.disabled = evalQuestions.length < 1;
  runEvalBtn.textContent = evalQuestions.length < 1
    ? '평가 실행 (최소 1개 질문 필요)'
    : `평가 실행 (${evalQuestions.length}개 질문)`;
}

runEvalBtn.addEventListener('click', runEvaluation);

async function runEvaluation() {
  if (!selectedMediaId) { alert('미디어를 먼저 선택하세요.'); return; }
  if (!evalQuestions.length) { alert('평가에 포함할 질문이 없습니다.'); return; }

  runEvalBtn.disabled = true;
  runEvalBtn.textContent = '평가 실행 중…';

  const params = new URLSearchParams({ test_questions: evalQuestions.join(',') });
  const ref = document.getElementById('wer-reference').value.trim();
  if (ref) params.set('reference_transcript', ref);
  try {
    const res = await fetch(`/media/${selectedMediaId}/evaluate?${params}`);
    const data = await res.json();
    renderEvalChart(data.metrics || data);
    evalResultRaw.textContent = JSON.stringify(data.metrics || data, null, 2);
    evalResultRaw.classList.remove('hidden');
  } catch (e) {
    evalResultRaw.textContent = '평가 실패: evaluation_utils를 구현하세요.';
    evalResultRaw.classList.remove('hidden');
  } finally {
    runEvalBtn.disabled = false;
    runEvalBtn.textContent = `평가 실행 (${evalQuestions.length}개 질문)`;
  }
}

function renderEvalChart(metrics) {
  evalChartWrap.classList.remove('hidden');
  const labels = [];
  const values = [];
  const targets = [];
  const METRIC_CONFIG = {
    answer_relevance:    { label: 'Answer Relevance', target: 0.70 },
    groundedness:        { label: 'Groundedness',     target: 0.70 },
    retrieval_precision: { label: 'Retrieval Precision', target: 0.60 },
    visual_text_alignment: { label: 'Visual-Text Alignment', target: 0.65 },
    wer:                 { label: 'WER (↓)',           target: 0.15 },
  };
  for (const [key, cfg] of Object.entries(METRIC_CONFIG)) {
    if (metrics[key] != null) {
      labels.push(cfg.label);
      values.push(parseFloat(metrics[key].toFixed(3)));
      targets.push(cfg.target);
    }
  }

  if (evalChart) evalChart.destroy();
  const ctx = document.getElementById('eval-chart').getContext('2d');
  evalChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: '현재 값',
          data: values,
          backgroundColor: values.map((v, i) => v >= targets[i] ? 'rgba(62,207,142,0.7)' : 'rgba(240,97,106,0.7)'),
          borderColor: values.map((v, i) => v >= targets[i] ? '#3ecf8e' : '#f0616a'),
          borderWidth: 1,
        },
        {
          label: '목표치',
          data: targets,
          type: 'line',
          borderColor: 'rgba(245,166,35,0.8)',
          borderDash: [5, 4],
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      scales: {
        y: { min: 0, max: 1, ticks: { color: '#8a90ad' }, grid: { color: '#2e3350' } },
        x: { ticks: { color: '#8a90ad' }, grid: { display: false } },
      },
      plugins: {
        legend: { labels: { color: '#e8eaf0' } },
      },
    },
  });
}

// ────────────────────────────────────────
// 유틸
// ────────────────────────────────────────
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function formatDuration(secs) {
  if (!secs) return '-';
  const m = Math.floor(secs / 60);
  const s = Math.round(secs % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

function formatTime(secs) {
  if (secs == null) return '?';
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
