const TASKS_URL = "../json/tasks_see2thinkbench_1200task_available.json";
const FULL_AUDIT_URL = "../outputs/strong_full_audit/audit_results.jsonl";
const YZR_CHECK_INDEX_URL = "../yzrcheck/index.csv";
const YZR_MISSING_INDEX_URL = "../yzrcheck/missing_13_from_2026-07-16T06-49-55-120Z.csv";
const YZR_CANDIDATE_MODE = "yzr_180";
const YZR_MISSING_MODE = "yzr_missing_13";

const SETTINGS = [
  { id: "full", label: "VAoT-Full", promptUrl: "../newprompt/see2think_vaot_full.txt" },
  { id: "text_only", label: "Text CoT", promptUrl: "../newprompt/see2think_text_cot.txt" },
  { id: "no_render", label: "VAoT-NoRender", promptUrl: "../newprompt/see2think_vaot_no_render.txt" },
  { id: "wrong_render", label: "WrongRender", promptUrl: "../newprompt/see2think_vaot_wrong_render.txt" },
];

const MODELS = [
  { id: "gpt-5.5", label: "GPT-5.5" },
  { id: "o3", label: "o3" },
  { id: "gemini-3.5-flash", label: "Gemini 3.5 Flash" },
  { id: "qwen3-vl-32b-thinking", label: "Qwen3-VL-32B" },
  { id: "qwen3-vl-8b-thinking", label: "Qwen3-VL-8B" },
];

const PROCESS_JUDGES = {
  "full::gpt-5.5": "../neweval/results/gpt54_judge_gpt55_final1200_vaot_full/process_judge.jsonl",
  "full::o3": "../neweval/results/gpt54_judge_o3_final1200_vaot_full/process_judge.jsonl",
  "full::gemini-3.5-flash": "../neweval/results/gpt54_judge_gemini35flash_final1200_vaot_full/process_judge.jsonl",
  "wrong_render::gpt-5.5": [
    "../neweval/results/gpt54_judge_gpt55_12_vaot_wrong_render/process_judge.jsonl",
    "../neweval/results/gpt54_judge_gpt55_final600_vaot_wrong_render/process_judge.jsonl",
  ],
  "wrong_render::o3": [
    "../neweval/results/gpt54_judge_o3_12_vaot_wrong_render/process_judge.jsonl",
    "../neweval/results/gpt54_judge_o3_final600_vaot_wrong_render/process_judge.jsonl",
  ],
  "wrong_render::gemini-3.5-flash": [
    "../neweval/results/gpt54_judge_gemini35flash_12_vaot_wrong_render/process_judge.jsonl",
    "../neweval/results/gpt54_judge_gemini35flash_final600_vaot_wrong_render/process_judge.jsonl",
  ],
};

const KEY_STEP_JUDGES = {
  "full::gpt-5.5": "../neweval/results/key_step_gpt55_final1200_vaot_full/key_step_judge.jsonl",
  "full::o3": "../neweval/results/key_step_o3_final1200_vaot_full/key_step_judge.jsonl",
  "full::gemini-3.5-flash": "../neweval/results/key_step_gemini35flash_final1200_vaot_full/key_step_judge.jsonl",
};

const ANSWER_JUDGES = {
  "full::gpt-5.5": "../neweval/results/answer_gpt55_final1200_vaot_full/answer_judge.jsonl",
  "full::o3": "../neweval/results/answer_o3_final1200_vaot_full/answer_judge.jsonl",
  "full::gemini-3.5-flash": "../neweval/results/answer_gemini35flash_final1200_vaot_full/answer_judge.jsonl",
  "full_600subset::gpt-5.5": "../neweval/results/answer_gpt55_final600subset_vaot_full/answer_judge.jsonl",
  "full_600subset::o3": "../neweval/results/answer_o3_final600subset_vaot_full/answer_judge.jsonl",
  "full_600subset::gemini-3.5-flash": "../neweval/results/answer_gemini35flash_final600subset_vaot_full/answer_judge.jsonl",
  "text_only::gpt-5.5": "../neweval/results/answer_gpt55_text_only_600/answer_judge.jsonl",
  "text_only::o3": "../neweval/results/answer_o3_text_only_600/answer_judge.jsonl",
  "text_only::gemini-3.5-flash": "../neweval/results/answer_gemini35flash_text_only_600/answer_judge.jsonl",
  "no_render::gpt-5.5": "../neweval/results/answer_gpt55_no_render_600/answer_judge.jsonl",
  "no_render::o3": "../neweval/results/answer_o3_no_render_600/answer_judge.jsonl",
  "no_render::gemini-3.5-flash": "../neweval/results/answer_gemini35flash_no_render_600/answer_judge.jsonl",
  "wrong_render::gpt-5.5": "../neweval/results/answer_gpt55_wrong_render_600/answer_judge.jsonl",
  "wrong_render::o3": "../neweval/results/answer_o3_wrong_render_600/answer_judge.jsonl",
  "wrong_render::gemini-3.5-flash": "../neweval/results/answer_gemini35flash_wrong_render_600/answer_judge.jsonl",
};

const SUMMARY_ANSWER_COLUMNS = [
  { id: "text_only", label: "Text CoT" },
  { id: "no_render", label: "VAoT-NoRender" },
  { id: "wrong_render", label: "WrongRender" },
  { id: "full_600subset", label: "VAoT-Full 600" },
  { id: "full", label: "VAoT-Full 1200" },
];

const MAX_RENDER_INDEX = 12;
const ANNOTATION_STORAGE_KEY = "see2think_human_annotations_v2_yzr_relabel";
const ANNOTATION_FIELDS = [
  {
    id: "key_step_selection",
    label: "Key-step selection",
    help: "Whether the judge-selected key visual step is relevant to final reasoning or exposes the failure source.",
  },
  {
    id: "action_relevance",
    label: "Action relevance",
    help: "Question + image before step + current thought + proposed action.",
  },
  {
    id: "render_faithfulness",
    label: "Render faithfulness",
    help: "Image before + action + rendered image after.",
  },
  {
    id: "feedback_uptake",
    label: "Feedback uptake",
    help: "Rendered image should affect subsequent reasoning; this is the most important item.",
  },
];
const ANNOTATION_VALUES = [
  { id: "reasonable", label: "Reasonable" },
  { id: "partial", label: "Partially reasonable" },
  { id: "unreasonable", label: "Unreasonable" },
];

const state = {
  tasks: [],
  process: new Map(),
  keySteps: new Map(),
  answers: new Map(),
  auditRows: [],
  auditByTaskModel: new Map(),
  auditByTask: new Map(),
  yzrRows: [],
  yzrByTask: new Map(),
  yzrByTaskModel: new Map(),
  yzrMissingRows: [],
  yzrMissingByTask: new Map(),
  yzrMissingByTaskModel: new Map(),
  promptTemplates: new Map(),
  dataCache: new Map(),
  selectedKey: null,
  enabledSettings: new Set(SETTINGS.map((s) => s.id)),
  enabledModels: new Set(MODELS.map((m) => m.id)),
  currentFiltered: [],
  annotations: loadAnnotations(),
};

const els = {
  loadStatus: document.getElementById("loadStatus"),
  searchInput: document.getElementById("searchInput"),
  familySelect: document.getElementById("familySelect"),
  answerSelect: document.getElementById("answerSelect"),
  candidateSelect: document.getElementById("candidateSelect"),
  listMeta: document.getElementById("listMeta"),
  taskList: document.getElementById("taskList"),
  taskHeader: document.getElementById("taskHeader"),
  summaryPanel: document.getElementById("summaryPanel"),
  questionText: document.getElementById("questionText"),
  sourceGrid: document.getElementById("sourceGrid"),
  originalImageWrap: document.getElementById("originalImageWrap"),
  settingToggles: document.getElementById("settingToggles"),
  modelToggles: document.getElementById("modelToggles"),
  modelPanels: document.getElementById("modelPanels"),
  imageModal: document.getElementById("imageModal"),
  modalImage: document.getElementById("modalImage"),
  closeModal: document.getElementById("closeModal"),
};

function runKey(settingId, modelId) {
  return `${settingId}::${modelId}`;
}

function modelTaskKey(modelId, taskKeyValue) {
  return `${modelId}::${taskKeyValue}`;
}

function relSourceDir(dataPath) {
  let p = String(dataPath || "").replaceAll("\\", "/");
  const prefix = "annotation/dataset/data/";
  if (p.startsWith(prefix)) p = p.slice(prefix.length);
  if (p.endsWith("/data.json")) p = p.slice(0, -"/data.json".length);
  return p;
}

function taskKey(task) {
  return `${relSourceDir(task.path)}::${Number(task.id)}`;
}

function outputDir(setting, model, task) {
  return `../final_results/${setting.id}/${model.id}/${relSourceDir(task.path)}/${Number(task.id)}`;
}

function escapeHtml(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function fetchText(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${url}`);
  return res.text();
}

async function fetchJson(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${url}`);
  return res.json();
}

function parseJsonl(text) {
  return text
    .split(/\r?\n/)
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
}

function parseCsv(text) {
  const lines = String(text || "").split(/\r?\n/).filter((line) => line.trim());
  if (!lines.length) return [];
  const headers = parseCsvLine(lines[0]);
  return lines.slice(1).map((line) => {
    const cells = parseCsvLine(line);
    const row = {};
    headers.forEach((header, idx) => {
      row[header] = cells[idx] ?? "";
    });
    return row;
  });
}

function parseCsvLine(line) {
  const cells = [];
  let current = "";
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === '"') {
      if (quoted && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        quoted = !quoted;
      }
    } else if (ch === "," && !quoted) {
      cells.push(current);
      current = "";
    } else {
      current += ch;
    }
  }
  cells.push(current);
  return cells;
}

async function loadJudgeMap(urlOrUrls) {
  const map = new Map();
  const urls = Array.isArray(urlOrUrls) ? urlOrUrls : [urlOrUrls];
  let loaded = 0;
  for (const url of urls) {
    try {
      const rows = parseJsonl(await fetchText(url));
      for (const row of rows) map.set(row.task_key, row);
      loaded += 1;
    } catch (err) {
      if (urls.length === 1) console.warn("optional judge map unavailable", url, err);
    }
  }
  if (!loaded && urls.length > 1) {
    console.warn("optional judge map unavailable", urls);
  }
  return map;
}

async function loadAuditRows(url) {
  try {
    return parseJsonl(await fetchText(url));
  } catch (err) {
    console.warn("optional full audit unavailable", url, err);
    return [];
  }
}

async function loadYzrCheckRows(url) {
  try {
    return parseCsv(await fetchText(url)).map((row) => ({
      ...row,
      case_index: Number(row.case_index),
      sample_id: Number(row.sample_id),
      full_correct: String(row.full_correct).toLowerCase() === "true",
      stratum_match: String(row.stratum_match).toLowerCase() === "true",
      action_relevance: Number(row.action_relevance),
      render_faithfulness: Number(row.render_faithfulness),
      feedback_uptake: Number(row.feedback_uptake),
    }));
  } catch (err) {
    console.warn("optional YZR check index unavailable", url, err);
    return [];
  }
}

async function loadPromptTemplate(setting) {
  try {
    return await fetchText(setting.promptUrl);
  } catch (err) {
    return `Prompt template not found: ${setting.promptUrl}`;
  }
}

async function loadAll() {
  renderToggles();
  const judgePromises = [];
  const judgeKeys = [];
  for (const [key, url] of Object.entries(PROCESS_JUDGES)) {
    judgeKeys.push(["process", key]);
    judgePromises.push(loadJudgeMap(url));
  }
  for (const [key, url] of Object.entries(KEY_STEP_JUDGES)) {
    judgeKeys.push(["keySteps", key]);
    judgePromises.push(loadJudgeMap(url));
  }
  for (const [key, url] of Object.entries(ANSWER_JUDGES)) {
    judgeKeys.push(["answers", key]);
    judgePromises.push(loadJudgeMap(url));
  }
  const promptPromises = SETTINGS.map((setting) => loadPromptTemplate(setting));
  const [tasks, judgeMaps, promptTemplates, auditRows, yzrRows, yzrMissingRows] = await Promise.all([
    fetchJson(TASKS_URL),
    Promise.all(judgePromises),
    Promise.all(promptPromises),
    loadAuditRows(FULL_AUDIT_URL),
    loadYzrCheckRows(YZR_CHECK_INDEX_URL),
    loadYzrCheckRows(YZR_MISSING_INDEX_URL),
  ]);

  state.tasks = tasks.map((task) => ({ ...task, key: taskKey(task), rel: relSourceDir(task.path) }));
  judgeMaps.forEach((map, idx) => {
    const [kind, key] = judgeKeys[idx];
    state[kind].set(key, map);
  });
  state.auditRows = auditRows;
  state.auditByTaskModel.clear();
  state.auditByTask.clear();
  for (const row of auditRows) {
    if (!row.task_key || !row.model) continue;
    state.auditByTaskModel.set(runKey(row.model, row.task_key), row);
    if (!state.auditByTask.has(row.task_key)) state.auditByTask.set(row.task_key, []);
    state.auditByTask.get(row.task_key).push(row);
  }
  state.yzrRows = yzrRows;
  state.yzrByTask.clear();
  state.yzrByTaskModel.clear();
  for (const row of yzrRows) {
    if (!row.task_key || !row.model) continue;
    if (!state.yzrByTask.has(row.task_key)) state.yzrByTask.set(row.task_key, []);
    state.yzrByTask.get(row.task_key).push(row);
    state.yzrByTaskModel.set(modelTaskKey(row.model, row.task_key), row);
  }
  for (const rows of state.yzrByTask.values()) rows.sort((a, b) => a.case_index - b.case_index);
  state.yzrMissingRows = yzrMissingRows;
  state.yzrMissingByTask.clear();
  state.yzrMissingByTaskModel.clear();
  for (const row of yzrMissingRows) {
    if (!row.task_key || !row.model) continue;
    if (!state.yzrMissingByTask.has(row.task_key)) state.yzrMissingByTask.set(row.task_key, []);
    state.yzrMissingByTask.get(row.task_key).push(row);
    state.yzrMissingByTaskModel.set(modelTaskKey(row.model, row.task_key), row);
  }
  for (const rows of state.yzrMissingByTask.values()) rows.sort((a, b) => a.case_index - b.case_index);
  SETTINGS.forEach((setting, idx) => state.promptTemplates.set(setting.id, promptTemplates[idx]));

  renderFamilyOptions();
  renderCandidateOptions();
  if (state.yzrMissingRows.length) els.candidateSelect.value = YZR_MISSING_MODE;
  else if (state.yzrRows.length) els.candidateSelect.value = YZR_CANDIDATE_MODE;
  renderSummary();
  bindEvents();
  applyFilters();
  els.loadStatus.textContent = `Loaded ${state.tasks.length} tasks; YZR check cases ${state.yzrRows.length}; missing ${state.yzrMissingRows.length}`;
}

function renderToggles() {
  els.settingToggles.innerHTML = `<button class="toggleBtn active" type="button" data-setting-all="1">All settings</button>` + SETTINGS.map(
    (setting) => `<button class="toggleBtn active" type="button" data-setting="${escapeHtml(setting.id)}">${escapeHtml(setting.label)}</button>`,
  ).join("");
  els.modelToggles.innerHTML = `<button class="toggleBtn active" type="button" data-model-all="1">All models</button>` + MODELS.map(
    (model) => `<button class="toggleBtn active" type="button" data-model="${escapeHtml(model.id)}">${escapeHtml(model.label)}</button>`,
  ).join("");
}

function renderFamilyOptions() {
  const families = [...new Set(state.tasks.map((t) => t.rel))].sort();
  els.familySelect.innerHTML = `<option value="all">All families</option>` + families.map((f) => `<option value="${escapeHtml(f)}">${escapeHtml(f)}</option>`).join("");
}

function loadedCandidateModels() {
  return MODELS.filter((model) => state.answers.has(runKey("full", model.id)) && state.process.has(runKey("full", model.id)));
}

function renderCandidateOptions() {
  const models = loadedCandidateModels();
  els.candidateSelect.innerHTML = [
    `<option value="all">All tasks</option>`,
    `<option value="${YZR_CANDIDATE_MODE}">YZR human validation 180</option>`,
    `<option value="${YZR_MISSING_MODE}">YZR missing 13</option>`,
    `<option value="strict_any">Strict best candidates: any model</option>`,
    ...models.map((model) => `<option value="strict::${escapeHtml(model.id)}">Strict: ${escapeHtml(model.label)}</option>`),
    `<option value="wr_success_any">WrongRender success: any model</option>`,
    ...models.map((model) => `<option value="wr_success::${escapeHtml(model.id)}">WrongRender success: ${escapeHtml(model.label)}</option>`),
    `<option value="audit_strong">Audit STRONG Full cases</option>`,
    `<option value="audit_midplus">Audit STRONG + MID Full cases</option>`,
    `<option value="audit_wrong_render_diag">Audit WrongRender diagnostic cases</option>`,
    `<option value="audit_grade::WEAK">Audit WEAK cases</option>`,
    `<option value="audit_grade::REJECT">Audit REJECT cases</option>`,
  ].join("");
}

function bindEvents() {
  els.searchInput.addEventListener("input", applyFilters);
  els.familySelect.addEventListener("change", applyFilters);
  els.answerSelect.addEventListener("change", applyFilters);
  els.candidateSelect.addEventListener("change", () => {
    renderSummary();
    applyFilters();
  });
  els.settingToggles.addEventListener("click", (event) => toggleSet(event, "setting"));
  els.modelToggles.addEventListener("click", (event) => toggleSet(event, "model"));
  els.summaryPanel.addEventListener("click", handleSummaryClick);
  els.modelPanels.addEventListener("change", handleAnnotationChange);
  els.modelPanels.addEventListener("input", handleAnnotationInput);
  els.closeModal.addEventListener("click", closeModal);
  els.imageModal.addEventListener("click", (event) => {
    if (event.target === els.imageModal) closeModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeModal();
  });
}

function toggleSet(event, type) {
  const attr = type === "setting" ? "setting" : "model";
  const allAttr = `${attr}All`;
  const allButton = event.target.closest(`[data-${attr}-all]`);
  const target = type === "setting" ? state.enabledSettings : state.enabledModels;
  const allItems = type === "setting" ? SETTINGS : MODELS;
  const root = type === "setting" ? els.settingToggles : els.modelToggles;
  if (allButton) {
    target.clear();
    allItems.forEach((item) => target.add(item.id));
    syncToggleButtons(root, attr, target);
    if (state.selectedKey) renderSelected();
    return;
  }

  const button = event.target.closest(`[data-${attr}]`);
  if (!button) return;
  const id = button.dataset[attr];
  target.clear();
  target.add(id);
  syncToggleButtons(root, attr, target);
  if (state.selectedKey) renderSelected();
}

function syncToggleButtons(root, attr, target) {
  const allCount = attr === "setting" ? SETTINGS.length : MODELS.length;
  root.querySelectorAll(`[data-${attr}]`).forEach((button) => {
    button.classList.toggle("active", target.has(button.dataset[attr]));
  });
  root.querySelector(`[data-${attr}-all]`)?.classList.toggle("active", target.size === allCount);
}

function fullAnswerRows(task) {
  return MODELS.map((model) => state.answers.get(runKey("full", model.id))?.get(task.key)).filter(Boolean);
}

function answerState(task) {
  const values = fullAnswerRows(task).map((row) => row.correct).filter((v) => typeof v === "boolean");
  const correct = values.filter(Boolean).length;
  return { total: values.length, correct, wrong: values.length - correct };
}

function passAnswerFilter(task, mode) {
  if (mode === "all") return true;
  const a = answerState(task);
  if (!a.total) return false;
  if (mode === "any_correct") return a.correct > 0;
  if (mode === "all_wrong") return a.correct === 0;
  if (mode === "mixed") return a.correct > 0 && a.wrong > 0;
  return true;
}

function strictCandidateForModel(task, modelId) {
  const answer = state.answers.get(runKey("full", modelId))?.get(task.key);
  const process = state.process.get(runKey("full", modelId))?.get(task.key);
  if (answer?.correct !== true || !process?.judge) return false;
  return ["action_relevance", "render_faithfulness", "feedback_uptake"].every(
    (metric) => process.judge?.[metric]?.score === 2,
  );
}

function strictCandidateModels(task) {
  return loadedCandidateModels().filter((model) => strictCandidateForModel(task, model.id));
}

function wrongRenderSuccessForModel(task, modelId) {
  const fullAnswer = state.answers.get(runKey("full", modelId))?.get(task.key);
  const wrongAnswer = state.answers.get(runKey("wrong_render", modelId))?.get(task.key);
  const fullProcess = state.process.get(runKey("full", modelId))?.get(task.key);
  const wrongProcess = state.process.get(runKey("wrong_render", modelId))?.get(task.key);
  if (fullAnswer?.correct !== true || wrongAnswer?.correct !== false) return false;
  if (!fullProcess?.judge || !wrongProcess?.judge) return false;
  const fullAllHigh = ["action_relevance", "render_faithfulness", "feedback_uptake"].every(
    (metric) => fullProcess.judge?.[metric]?.score === 2,
  );
  if (!fullAllHigh) return false;
  const wrongRenderScore = wrongProcess.judge?.render_faithfulness?.score;
  return wrongProcess.judge?.feedback_uptake?.score === 2
    && typeof wrongRenderScore === "number"
    && wrongRenderScore <= 1;
}

function wrongRenderSuccessModels(task) {
  return loadedCandidateModels().filter((model) => wrongRenderSuccessForModel(task, model.id));
}

function auditRowsForTask(task) {
  return state.auditByTask.get(task.key) || [];
}

function auditRowForTaskModel(task, modelId) {
  return state.auditByTaskModel.get(runKey(modelId, task.key));
}

function yzrRowsForTask(task) {
  return yzrRowsForTaskMode(task, els.candidateSelect.value);
}

function yzrRowsForTaskMode(task, mode) {
  if (mode === YZR_MISSING_MODE) return state.yzrMissingByTask.get(task.key) || [];
  return state.yzrByTask.get(task.key) || [];
}

function yzrRowForTaskModel(task, modelId) {
  const map = els.candidateSelect.value === YZR_MISSING_MODE ? state.yzrMissingByTaskModel : state.yzrByTaskModel;
  return map.get(modelTaskKey(modelId, task.key));
}

function yzrModelsForTask(task) {
  return new Set(yzrRowsForTask(task).map((row) => row.model));
}

function isYzrMode() {
  return els.candidateSelect.value === YZR_CANDIDATE_MODE || els.candidateSelect.value === YZR_MISSING_MODE;
}

function isYzrMissingMode() {
  return els.candidateSelect.value === YZR_MISSING_MODE;
}

function activeYzrRows() {
  return isYzrMissingMode() ? state.yzrMissingRows : state.yzrRows;
}

function bestAuditRows(task, grades) {
  const allowed = new Set(grades);
  return auditRowsForTask(task)
    .filter((row) => allowed.has(row.grade))
    .sort((a, b) => (b.total_score || 0) - (a.total_score || 0));
}

function passCandidateFilter(task, mode) {
  if (!mode || mode === "all") return true;
  if (mode === YZR_CANDIDATE_MODE) return yzrRowsForTask(task).length > 0;
  if (mode === YZR_MISSING_MODE) return yzrRowsForTaskMode(task, mode).length > 0;
  if (mode === "strict_any") return strictCandidateModels(task).length > 0;
  if (mode.startsWith("strict::")) return strictCandidateForModel(task, mode.slice("strict::".length));
  if (mode === "wr_success_any") return wrongRenderSuccessModels(task).length > 0;
  if (mode.startsWith("wr_success::")) return wrongRenderSuccessForModel(task, mode.slice("wr_success::".length));
  if (mode === "audit_strong") return bestAuditRows(task, ["STRONG"]).length > 0;
  if (mode === "audit_midplus") return bestAuditRows(task, ["STRONG", "MID"]).length > 0;
  if (mode === "audit_wrong_render_diag") return bestAuditRows(task, ["WRONG_RENDER_DIAGNOSTIC"]).length > 0;
  if (mode.startsWith("audit_grade::")) return bestAuditRows(task, [mode.slice("audit_grade::".length)]).length > 0;
  return true;
}

function summarizeStrictCandidates() {
  const models = loadedCandidateModels();
  const byModel = models.map((model) => {
    const tasks = state.tasks.filter((task) => strictCandidateForModel(task, model.id));
    return { model, count: tasks.length };
  });
  const anyKeys = new Set();
  for (const task of state.tasks) {
    if (strictCandidateModels(task).length) anyKeys.add(task.key);
  }
  return { anyCount: anyKeys.size, byModel };
}

function summarizeWrongRenderSuccess() {
  const models = loadedCandidateModels();
  const byModel = models.map((model) => {
    const tasks = state.tasks.filter((task) => wrongRenderSuccessForModel(task, model.id));
    const renderZero = tasks.filter((task) => state.process.get(runKey("wrong_render", model.id))?.get(task.key)?.judge?.render_faithfulness?.score === 0).length;
    return { model, count: tasks.length, renderZero };
  });
  const anyKeys = new Set();
  for (const task of state.tasks) {
    if (wrongRenderSuccessModels(task).length) anyKeys.add(task.key);
  }
  return { anyCount: anyKeys.size, byModel };
}

function summarizeFullAudit() {
  const counts = {};
  for (const row of state.auditRows) {
    counts[row.grade || "UNKNOWN"] = (counts[row.grade || "UNKNOWN"] || 0) + 1;
  }
  const top = [...state.auditRows]
    .filter((row) => row.grade === "STRONG" || row.grade === "MID")
    .sort((a, b) => (b.total_score || 0) - (a.total_score || 0))
    .slice(0, 8);
  return { counts, top };
}

function pct(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "n/a";
  return `${(value * 100).toFixed(1)}%`;
}

function summarizeAnswer(settingId, modelId) {
  const rows = [...(state.answers.get(runKey(settingId, modelId))?.values() || [])]
    .filter((row) => typeof row.correct === "boolean");
  const correct = rows.filter((row) => row.correct).length;
  return { total: rows.length, correct, accuracy: rows.length ? correct / rows.length : null };
}

function summarizeProcess(settingId, modelId) {
  const rows = [...(state.process.get(runKey(settingId, modelId))?.values() || [])];
  const metrics = ["action_relevance", "render_faithfulness", "feedback_uptake"];
  const out = { total: rows.length };
  for (const metric of metrics) {
    const values = rows
      .map((row) => row.judge?.[metric]?.normalized_score)
      .filter((value) => typeof value === "number");
    out[metric] = values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  }
  return out;
}

function renderSummary() {
  if (isYzrMode()) {
    const title = isYzrMissingMode() ? "YZR Missing 13" : "YZR Human Validation 180";
    const hint = isYzrMissingMode()
      ? "Only the 13 unannotated sampled VAoT-Full model-task cases are shown. Annotate all cards marked ANNOTATE YZR #..."
      : "Only sampled VAoT-Full model-task cases are shown. Annotate the cards marked ANNOTATE YZR #...";
    els.summaryPanel.innerHTML = `
      <div class="summaryHeader">
        <div>
          <div class="panelTitle">${escapeHtml(title)}</div>
          <div class="summaryHint">${escapeHtml(hint)}</div>
        </div>
        <div class="annotationActions">
          <span class="badge">${annotationCount()} annotations</span>
          <button class="smallBtn" type="button" data-export-annotations="json">Export JSON</button>
          <button class="smallBtn" type="button" data-export-annotations="csv">Export CSV</button>
        </div>
      </div>
      <details class="guidelineBox" open>
        <summary>Human annotation guideline</summary>
        <div class="guidelineGrid">
          <div><strong>Key-step selection</strong><span>Judge whether the selected key visual step is reasonable.</span></div>
          <div><strong>Action relevance</strong><span>Judge using only question, image before the step, current thought, and proposed action.</span></div>
          <div><strong>Render faithfulness</strong><span>Judge whether the rendered image faithfully executes the proposed visual action.</span></div>
          <div><strong>Feedback uptake</strong><span>Judge whether subsequent reasoning actually depends on the rendered image.</span></div>
        </div>
        <div class="summaryHint">Use: Reasonable / Partially reasonable / Unreasonable. Export after finishing the 180 model-task cases.</div>
      </details>
      <details open>
        <summary>Human annotation report</summary>
        <div data-annotation-report>${annotationReportHtml()}</div>
      </details>`;
    return;
  }

  const processRows = [];
  for (const setting of SETTINGS) {
    for (const model of MODELS) {
      const process = summarizeProcess(setting.id, model.id);
      if (!process.total) continue;
      processRows.push({ setting, model, process });
    }
  }

  const answerHtml = renderAnswerComparison();
  const candidateHtml = renderStrictCandidateSummary();
  const wrongRenderCandidateHtml = renderWrongRenderSuccessSummary();
  const fullAuditHtml = renderFullAuditSummary();

  const processHtml = processRows.length ? `
    <table class="summaryTable">
      <thead>
        <tr>
          <th>Setting</th>
          <th>Model</th>
          <th>Action</th>
          <th>Render</th>
          <th>Uptake</th>
          <th>N</th>
        </tr>
      </thead>
      <tbody>
        ${processRows.map(({ setting, model, process }) => `
          <tr>
            <td>${escapeHtml(setting.label)}</td>
            <td>${escapeHtml(model.label)}</td>
            <td>${pct(process.action_relevance)}</td>
            <td>${pct(process.render_faithfulness)}</td>
            <td>${pct(process.feedback_uptake)}</td>
            <td>${process.total}</td>
          </tr>`).join("")}
      </tbody>
    </table>` : `<div class="empty">No process judge summary loaded.</div>`;

  els.summaryPanel.innerHTML = `
    <div class="summaryHeader">
      <div>
        <div class="panelTitle">Summary</div>
        <div class="summaryHint">ACC comparison includes the matched 600-task subset and an additional Full-1200 column. Task badges still use the full 1200 VAoT-Full results.</div>
      </div>
      <div class="annotationActions">
        <span class="badge">${annotationCount()} annotations</span>
        <button class="smallBtn" type="button" data-export-annotations="json">Export JSON</button>
        <button class="smallBtn" type="button" data-export-annotations="csv">Export CSV</button>
      </div>
    </div>
    <details class="guidelineBox">
      <summary>Human annotation guideline</summary>
      <div class="guidelineGrid">
        <div><strong>Key visual step</strong><span>Whether the selected key step is relevant to final reasoning or exposes the failure source.</span></div>
        <div><strong>Action relevance</strong><span>Whether the proposed visual action is related to the question and targets the right evidence.</span></div>
        <div><strong>Render faithfulness</strong><span>Whether the rendered image faithfully executes the action: target, position, line/box/text/crop, and no major omission.</span></div>
        <div><strong>Feedback uptake</strong><span>Whether subsequent reasoning actually uses the rendered image instead of only repeating the action text.</span></div>
      </div>
      <div class="summaryHint">Use: Reasonable / Partially reasonable / Unreasonable. Report Reasonable rate and Reasonable-or-partial rate.</div>
    </details>
    <details>
      <summary>Human annotation report</summary>
      <div data-annotation-report>${annotationReportHtml()}</div>
    </details>
    <details open>
      <summary>Answer ACC</summary>
      ${answerHtml}
    </details>
    <details open>
      <summary>Strict best candidate set</summary>
      ${candidateHtml}
    </details>
    <details open>
      <summary>WrongRender successful misleading cases</summary>
      ${wrongRenderCandidateHtml}
    </details>
    <details open>
      <summary>Strong Full audit</summary>
      ${fullAuditHtml}
    </details>
    <details>
      <summary>Process judge averages</summary>
      ${processHtml}
    </details>`;
}

function annotationCount() {
  if (isYzrMode()) return annotationRowsForReport().length;
  return Object.keys(state.annotations || {}).length;
}

function loadAnnotations() {
  try {
    return JSON.parse(localStorage.getItem(ANNOTATION_STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveAnnotations() {
  localStorage.setItem(ANNOTATION_STORAGE_KEY, JSON.stringify(state.annotations));
  const badge = els.summaryPanel.querySelector(".annotationActions .badge");
  if (badge) badge.textContent = `${annotationCount()} annotations`;
  const report = els.summaryPanel.querySelector("[data-annotation-report]");
  if (report) report.innerHTML = annotationReportHtml();
}

function annotationReportHtml() {
  const rows = annotationRowsForReport();
  if (!rows.length) return `<div class="empty">No human annotations yet.</div>`;
  return `
    <table class="summaryTable">
      <thead>
        <tr>
          <th>Annotation target</th>
          <th>N</th>
          <th>Reasonable</th>
          <th>Reasonable or partial</th>
        </tr>
      </thead>
      <tbody>
        ${ANNOTATION_FIELDS.map((field) => {
          const values = rows.map((row) => row[field.id]).filter(Boolean);
          const n = values.length;
          const reasonable = values.filter((v) => v === "reasonable").length;
          const okPartial = values.filter((v) => v === "reasonable" || v === "partial").length;
          return `
            <tr>
              <td>${escapeHtml(field.label)}</td>
              <td>${n}</td>
              <td>${n ? `${(reasonable * 100 / n).toFixed(1)}%` : "n/a"}</td>
              <td>${n ? `${(okPartial * 100 / n).toFixed(1)}%` : "n/a"}</td>
            </tr>`;
        }).join("")}
      </tbody>
    </table>`;
}

function annotationRowsForReport() {
  const rows = isYzrMode()
    ? yzrAnnotationRows()
    : Object.values(state.annotations || {});
  return rows.filter((row) =>
    ANNOTATION_FIELDS.some((field) => row[field.id])
    || row.key_step_selection
    || row.note
  );
}

function annotationKey(taskKeyValue, settingId, modelId) {
  return `${settingId}::${modelId}::${taskKeyValue}`;
}

function getAnnotation(taskKeyValue, settingId, modelId) {
  return state.annotations[annotationKey(taskKeyValue, settingId, modelId)] || {};
}

function setAnnotationValue(taskKeyValue, settingId, modelId, patch) {
  const key = annotationKey(taskKeyValue, settingId, modelId);
  const prev = state.annotations[key] || {};
  state.annotations[key] = {
    ...prev,
    ...patch,
    task_key: taskKeyValue,
    setting: settingId,
    model: modelId,
    updated_at: new Date().toISOString(),
  };
  saveAnnotations();
}

function handleSummaryClick(event) {
  const exportButton = event.target.closest("[data-export-annotations]");
  if (exportButton) {
    exportAnnotations(exportButton.dataset.exportAnnotations);
    return;
  }
  const candidateButton = event.target.closest("[data-candidate-filter]");
  if (candidateButton) {
    els.candidateSelect.value = candidateButton.dataset.candidateFilter;
    applyFilters();
    return;
  }
  const auditOpenButton = event.target.closest("[data-open-audit-task]");
  if (auditOpenButton) {
    const key = auditOpenButton.dataset.openAuditTask;
    els.candidateSelect.value = auditOpenButton.dataset.auditFilter || "audit_midplus";
    applyFilters();
    state.selectedKey = key;
    renderTaskList();
    renderSelected();
    document.querySelector(".taskHeader")?.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  const candidateExport = event.target.closest("[data-export-candidates]");
  if (candidateExport) {
    exportStrictCandidates(candidateExport.dataset.exportCandidates);
    return;
  }
  const wrongRenderExport = event.target.closest("[data-export-wrong-render-candidates]");
  if (wrongRenderExport) {
    exportWrongRenderSuccess(wrongRenderExport.dataset.exportWrongRenderCandidates);
  }
}

function handleAnnotationChange(event) {
  const input = event.target.closest("[data-annotation-field]");
  if (!input) return;
  const root = input.closest("[data-annotation-root]");
  if (!root) return;
  setAnnotationValue(root.dataset.taskKey, root.dataset.setting, root.dataset.model, {
    [input.dataset.annotationField]: input.value,
  });
  markAnnotationSaved(root);
}

function handleAnnotationInput(event) {
  const input = event.target.closest("[data-annotation-text]");
  if (!input) return;
  const root = input.closest("[data-annotation-root]");
  if (!root) return;
  setAnnotationValue(root.dataset.taskKey, root.dataset.setting, root.dataset.model, {
    [input.dataset.annotationText]: input.value,
  });
  markAnnotationSaved(root);
}

function markAnnotationSaved(root) {
  const saved = root.querySelector(".annotationSaved");
  if (!saved) return;
  saved.textContent = "Saved";
  window.clearTimeout(root._savedTimer);
  root._savedTimer = window.setTimeout(() => { saved.textContent = ""; }, 1200);
}

function exportAnnotations(format) {
  const rows = isYzrMode() ? yzrAnnotationRows() : Object.values(state.annotations || {});
  const prefix = isYzrMissingMode() ? "yzrcheck_missing_13_annotations" : (isYzrMode() ? "yzrcheck_human_annotations_180" : "see2think_human_annotations");
  if (format === "csv") {
    const fields = isYzrMode()
      ? [
        "case_index",
        "task_group",
        "stratum",
        "stratum_match",
        "task_key",
        "setting",
        "model",
        "relative_source_dir",
        "sample_id",
        "case_dir",
        ...ANNOTATION_FIELDS.map((f) => f.id),
        "note",
        "updated_at",
      ]
      : ["task_key", "setting", "model", ...ANNOTATION_FIELDS.map((f) => f.id), "note", "updated_at"];
    const csv = [
      fields.join(","),
      ...rows.map((row) => fields.map((field) => csvCell(row[field] ?? "")).join(",")),
    ].join("\n");
    downloadText(`${prefix}_${timestampSlug()}.csv`, csv, "text/csv;charset=utf-8");
    return;
  }
  downloadText(
    `${prefix}_${timestampSlug()}.json`,
    JSON.stringify({ exported_at: new Date().toISOString(), count: rows.length, annotations: rows }, null, 2),
    "application/json;charset=utf-8",
  );
}

function yzrAnnotationRows() {
  return [...activeYzrRows()]
    .sort((a, b) => a.case_index - b.case_index)
    .map((row) => {
      const ann = getAnnotation(row.task_key, "full", row.model);
      return {
        case_index: row.case_index,
        task_group: row.task_group,
        stratum: row.stratum,
        stratum_match: row.stratum_match,
        task_key: row.task_key,
        setting: "full",
        model: row.model,
        relative_source_dir: row.relative_source_dir,
        sample_id: row.sample_id,
        case_dir: row.case_dir,
        ...ann,
      };
    });
}

function strictCandidateRows() {
  return state.tasks.flatMap((task) => {
    const models = strictCandidateModels(task);
    if (!models.length) return [];
    return models.map((model) => {
      const answer = state.answers.get(runKey("full", model.id))?.get(task.key);
      const process = state.process.get(runKey("full", model.id))?.get(task.key);
      return {
        task_key: task.key,
        order: Number(task.order),
        sample_id: Number(task.id),
        relative_source_dir: task.rel,
        category: task.category || "",
        target_task: task.target_task || "",
        source: task.source || "",
        path: task.path || "",
        model: model.id,
        model_label: model.label,
        answer_correct: answer?.correct === true,
        action_relevance: process?.judge?.action_relevance?.score,
        render_faithfulness: process?.judge?.render_faithfulness?.score,
        feedback_uptake: process?.judge?.feedback_uptake?.score,
      };
    });
  });
}

function exportStrictCandidates(format) {
  const rows = strictCandidateRows();
  if (format === "csv") {
    const fields = [
      "task_key",
      "order",
      "sample_id",
      "relative_source_dir",
      "category",
      "target_task",
      "source",
      "path",
      "model",
      "model_label",
      "answer_correct",
      "action_relevance",
      "render_faithfulness",
      "feedback_uptake",
    ];
    const csv = [
      fields.join(","),
      ...rows.map((row) => fields.map((field) => csvCell(row[field] ?? "")).join(",")),
    ].join("\n");
    downloadText(`see2think_strict_candidates_${timestampSlug()}.csv`, csv, "text/csv;charset=utf-8");
    return;
  }
  downloadText(
    `see2think_strict_candidates_${timestampSlug()}.json`,
    JSON.stringify({ exported_at: new Date().toISOString(), count: rows.length, candidates: rows }, null, 2),
    "application/json;charset=utf-8",
  );
}

function wrongRenderSuccessRows() {
  return state.tasks.flatMap((task) => {
    const models = wrongRenderSuccessModels(task);
    if (!models.length) return [];
    return models.map((model) => {
      const fullProcess = state.process.get(runKey("full", model.id))?.get(task.key);
      const wrongProcess = state.process.get(runKey("wrong_render", model.id))?.get(task.key);
      const fullAnswer = state.answers.get(runKey("full", model.id))?.get(task.key);
      const wrongAnswer = state.answers.get(runKey("wrong_render", model.id))?.get(task.key);
      const textAnswer = state.answers.get(runKey("text_only", model.id))?.get(task.key);
      const noRenderAnswer = state.answers.get(runKey("no_render", model.id))?.get(task.key);
      const keyStep = state.keySteps.get(runKey("full", model.id))?.get(task.key);
      return {
        task_key: task.key,
        order: Number(task.order),
        sample_id: Number(task.id),
        relative_source_dir: task.rel,
        category: task.category || "",
        target_task: task.target_task || "",
        source: task.source || "",
        path: task.path || "",
        model: model.id,
        model_label: model.label,
        text_cot_correct: textAnswer?.correct,
        no_render_correct: noRenderAnswer?.correct,
        full_correct: fullAnswer?.correct,
        wrong_render_correct: wrongAnswer?.correct,
        full_action_relevance: fullProcess?.judge?.action_relevance?.score,
        full_render_faithfulness: fullProcess?.judge?.render_faithfulness?.score,
        full_feedback_uptake: fullProcess?.judge?.feedback_uptake?.score,
        wrong_render_render_faithfulness: wrongProcess?.judge?.render_faithfulness?.score,
        wrong_render_feedback_uptake: wrongProcess?.judge?.feedback_uptake?.score,
        full_key_steps: JSON.stringify(keyStep?.key_steps || []),
        no_valid_visual_step: keyStep?.no_valid_visual_step,
        manual_check_corrupted_step_hits_key_step: "",
        manual_check_corruption_changes_key_evidence: "",
      };
    });
  });
}

function exportWrongRenderSuccess(format) {
  const rows = wrongRenderSuccessRows();
  if (format === "csv") {
    const fields = [
      "task_key",
      "order",
      "sample_id",
      "relative_source_dir",
      "category",
      "target_task",
      "source",
      "path",
      "model",
      "model_label",
      "text_cot_correct",
      "no_render_correct",
      "full_correct",
      "wrong_render_correct",
      "full_action_relevance",
      "full_render_faithfulness",
      "full_feedback_uptake",
      "wrong_render_render_faithfulness",
      "wrong_render_feedback_uptake",
      "full_key_steps",
      "no_valid_visual_step",
      "manual_check_corrupted_step_hits_key_step",
      "manual_check_corruption_changes_key_evidence",
    ];
    const csv = [
      fields.join(","),
      ...rows.map((row) => fields.map((field) => csvCell(row[field] ?? "")).join(",")),
    ].join("\n");
    downloadText(`see2think_wrong_render_success_${timestampSlug()}.csv`, csv, "text/csv;charset=utf-8");
    return;
  }
  downloadText(
    `see2think_wrong_render_success_${timestampSlug()}.json`,
    JSON.stringify({ exported_at: new Date().toISOString(), count: rows.length, candidates: rows }, null, 2),
    "application/json;charset=utf-8",
  );
}

function csvCell(value) {
  const s = String(value ?? "");
  return /[",\n\r]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
}

function timestampSlug() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function downloadText(filename, text, type) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function renderAnswerComparison() {
  const loadedModels = MODELS
    .map((model) => ({ model, cells: SUMMARY_ANSWER_COLUMNS.map((column) => summarizeAnswer(column.id, model.id)) }))
    .filter(({ cells }) => cells.some((cell) => cell.total));
  if (!loadedModels.length) return `<div class="empty">No answer ACC loaded.</div>`;

  return `
    <table class="summaryTable answerCompareTable">
      <thead>
        <tr>
          <th>Model</th>
          ${SUMMARY_ANSWER_COLUMNS.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("")}
        </tr>
      </thead>
      <tbody>
        ${loadedModels.map(({ model, cells }) => `
          <tr>
            <td><strong>${escapeHtml(model.label)}</strong></td>
            ${cells.map((answer) => `
              <td>
                ${answer.total ? `
                  <div class="accValue">${pct(answer.accuracy)}</div>
                  <div class="summarySub">${answer.correct}/${answer.total}</div>
                ` : `<span class="muted">not loaded</span>`}
              </td>`).join("")}
          </tr>`).join("")}
      </tbody>
    </table>`;
}

function renderStrictCandidateSummary() {
  const summary = summarizeStrictCandidates();
  if (!summary.byModel.length) return `<div class="empty">No Full answer/process judge pairs loaded for strict candidate filtering.</div>`;
  return `
    <div class="candidateSummary">
      <div class="candidateCriteria">
        <strong>Criteria</strong>
        <code>answer_correct = true</code>
        <code>action_relevance = 2</code>
        <code>render_faithfulness = 2</code>
        <code>feedback_uptake = 2</code>
      </div>
      <div class="candidateCards">
        <button class="candidateCard" type="button" data-candidate-filter="strict_any">
          <span>Any loaded model</span>
          <strong>${summary.anyCount}</strong>
          <em>tasks</em>
        </button>
        ${summary.byModel.map(({ model, count }) => `
          <button class="candidateCard" type="button" data-candidate-filter="strict::${escapeHtml(model.id)}">
            <span>${escapeHtml(model.label)}</span>
            <strong>${count}</strong>
            <em>tasks</em>
          </button>`).join("")}
      </div>
      <div class="candidateActions">
        <button class="smallBtn" type="button" data-export-candidates="json">Export candidates JSON</button>
        <button class="smallBtn" type="button" data-export-candidates="csv">Export candidates CSV</button>
      </div>
      <div class="summaryHint">Click a card to filter the left task list. These are strict Full candidates only; missing judge rows are excluded. Export rows are per task-model candidate.</div>
    </div>`;
}

function renderWrongRenderSuccessSummary() {
  const summary = summarizeWrongRenderSuccess();
  if (!summary.byModel.length) return `<div class="empty">No WrongRender answer/process judge pairs loaded. Run process eval for VAoT-WrongRender to enable this candidate set.</div>`;
  const processCounts = summary.byModel.map(({ model }) => state.process.get(runKey("wrong_render", model.id))?.size || 0);
  const maxLoaded = Math.max(0, ...processCounts);
  return `
    <div class="candidateSummary wrongRenderCandidateSummary">
      <div class="candidateCriteria">
        <strong>Criteria</strong>
        <code>Full correct</code>
        <code>WrongRender wrong</code>
        <code>Full action/render/uptake = 2</code>
        <code>WrongRender uptake = 2</code>
        <code>WrongRender render <= 1</code>
      </div>
      ${maxLoaded < 600 ? `<div class="warningBox">Only ${maxLoaded} WrongRender process-judge rows are currently loaded per model at most. For 600-case selection, run VAoT-WrongRender process eval first.</div>` : ""}
      <div class="candidateCards">
        <button class="candidateCard wrongRenderCard" type="button" data-candidate-filter="wr_success_any">
          <span>Any loaded model</span>
          <strong>${summary.anyCount}</strong>
          <em>tasks</em>
        </button>
        ${summary.byModel.map(({ model, count, renderZero }) => `
          <button class="candidateCard wrongRenderCard" type="button" data-candidate-filter="wr_success::${escapeHtml(model.id)}">
            <span>${escapeHtml(model.label)}</span>
            <strong>${count}</strong>
            <em>${renderZero} with WR render = 0</em>
          </button>`).join("")}
      </div>
      <div class="candidateActions">
        <button class="smallBtn" type="button" data-export-wrong-render-candidates="json">Export WrongRender JSON</button>
        <button class="smallBtn" type="button" data-export-wrong-render-candidates="csv">Export WrongRender CSV</button>
      </div>
      <div class="summaryHint">After export, manually check whether the corrupted step hits the full key visual step and whether the corruption changes task-relevant evidence.</div>
    </div>`;
}

function renderFullAuditSummary() {
  const summary = summarizeFullAudit();
  if (!state.auditRows.length) return `<div class="empty">No strong Full audit loaded. Run scripts/find_strong_full_cases.py first.</div>`;
  const gradeOrder = ["STRONG", "MID", "WEAK", "REJECT", "WRONG_RENDER_DIAGNOSTIC"];
  return `
    <div class="candidateSummary fullAuditSummary">
      <div class="candidateCards">
        ${gradeOrder.filter((grade) => summary.counts[grade]).map((grade) => `
          <button class="candidateCard auditCard" type="button" data-candidate-filter="${grade === "STRONG" ? "audit_strong" : grade === "WRONG_RENDER_DIAGNOSTIC" ? "audit_wrong_render_diag" : `audit_grade::${escapeHtml(grade)}`}">
            <span>${escapeHtml(grade)}</span>
            <strong>${summary.counts[grade]}</strong>
            <em>model-task rows</em>
          </button>`).join("")}
      </div>
      <div class="summaryHint">Audit rows are model-task level. STRONG requires total >= 11, D/E/F = 2, render correctness = 2, and final answer correct.</div>
      <table class="summaryTable">
        <thead><tr><th>Top strongest</th><th>Grade</th><th>Score</th><th>Why</th><th></th></tr></thead>
        <tbody>
          ${summary.top.map((row) => `
            <tr>
              <td>${escapeHtml(row.task_id)}</td>
              <td>${escapeHtml(row.grade)}</td>
              <td>${row.total_score}/14</td>
              <td>${escapeHtml(row.why_possible_strong || "")}</td>
              <td><button class="smallBtn" type="button" data-open-audit-task="${escapeHtml(row.task_key)}" data-audit-filter="${row.grade === "STRONG" ? "audit_strong" : "audit_midplus"}">Open</button></td>
            </tr>`).join("")}
        </tbody>
      </table>
      <div class="candidateActions">
        <a class="smallBtn linkBtn" href="../outputs/strong_full_audit/strong_full_candidates.md" target="_blank">Open candidates MD</a>
        <a class="smallBtn linkBtn" href="../outputs/strong_full_audit/review_gallery.html" target="_blank">Open review gallery</a>
      </div>
    </div>`;
}

function applyFilters() {
  const q = els.searchInput.value.trim().toLowerCase();
  const family = els.familySelect.value;
  const answerMode = els.answerSelect.value;
  const candidateMode = els.candidateSelect.value;
  state.currentFiltered = state.tasks.filter((task) => {
    if (family !== "all" && task.rel !== family) return false;
    if (!passAnswerFilter(task, answerMode)) return false;
    if (!passCandidateFilter(task, candidateMode)) return false;
    if (!q) return true;
    const haystack = [task.order, task.id, task.key, task.category, task.target_task, task.source, task.path, task.rel].join(" ").toLowerCase();
    return haystack.includes(q);
  });
  if (candidateMode?.startsWith("audit_")) {
    state.currentFiltered.sort((a, b) => bestAuditScore(b) - bestAuditScore(a) || Number(a.order) - Number(b.order));
  }
  if (candidateMode === YZR_CANDIDATE_MODE || candidateMode === YZR_MISSING_MODE) {
    state.currentFiltered.sort((a, b) => {
      const aCase = Math.min(...yzrRowsForTaskMode(a, candidateMode).map((row) => row.case_index));
      const bCase = Math.min(...yzrRowsForTaskMode(b, candidateMode).map((row) => row.case_index));
      return aCase - bCase || Number(a.order) - Number(b.order);
    });
  }
  if (!state.selectedKey || !state.currentFiltered.some((t) => t.key === state.selectedKey)) {
    state.selectedKey = state.currentFiltered[0]?.key ?? null;
  }
  renderTaskList();
  renderSelected();
}

function bestAuditScore(task) {
  return Math.max(-1, ...auditRowsForTask(task).map((row) => Number(row.total_score) || 0));
}

function renderTaskList() {
  const yzrCaseCount = isYzrMode()
    ? state.currentFiltered.reduce((sum, task) => sum + yzrRowsForTask(task).length, 0)
    : null;
  els.listMeta.textContent = isYzrMode()
    ? `${state.currentFiltered.length} tasks shown / ${yzrCaseCount} YZR model-task cases`
    : `${state.currentFiltered.length} tasks shown`;
  els.taskList.innerHTML = state.currentFiltered.map((task) => {
    const active = task.key === state.selectedKey ? " active" : "";
    const candidates = strictCandidateModels(task);
    const wrongRenderCandidates = wrongRenderSuccessModels(task);
    const auditCandidates = bestAuditRows(task, ["STRONG", "MID", "WRONG_RENDER_DIAGNOSTIC"]).slice(0, 3);
    const badges = isYzrMode() ? "" : MODELS.slice(0, 3).map((model) => {
      const answer = state.answers.get(runKey("full", model.id))?.get(task.key);
      if (!answer) return `<span class="badge warn">${escapeHtml(shortModel(model.id))} ?</span>`;
      return `<span class="badge ${answer.correct ? "good" : "bad"}">${escapeHtml(shortModel(model.id))} ${answer.correct ? "OK" : "Wrong"}</span>`;
    }).join("");
    const candidateBadges = candidates.length
      ? `<div class="miniBadges candidateMiniBadges">${candidates.map((model) => `<span class="badge candidate">Strict ${escapeHtml(shortModel(model.id))}</span>`).join("")}</div>`
      : "";
    const wrongRenderBadges = wrongRenderCandidates.length
      ? `<div class="miniBadges candidateMiniBadges">${wrongRenderCandidates.map((model) => `<span class="badge wrongRenderCandidate">WR mislead ${escapeHtml(shortModel(model.id))}</span>`).join("")}</div>`
      : "";
    const auditBadges = auditCandidates.length
      ? `<div class="miniBadges candidateMiniBadges">${auditCandidates.map((row) => `<span class="badge audit ${auditClass(row.grade)}">${escapeHtml(row.grade)} ${escapeHtml(shortModel(row.model))} ${row.total_score}/14</span>`).join("")}</div>`
      : "";
    const yzrBadges = yzrRowsForTask(task).length
      ? `<div class="miniBadges candidateMiniBadges">${yzrRowsForTask(task).map((row) => `<span class="badge auditDiagnostic">YZR #${escapeHtml(row.case_index)} ${escapeHtml(shortModel(row.model))} ${escapeHtml(row.task_group)} ${escapeHtml(row.stratum)}${row.stratum_match ? "" : " supplement"}</span>`).join("")}</div>`
      : "";
    return `
      <button class="taskItem${active}" type="button" data-key="${escapeHtml(task.key)}">
        <div class="taskItemTop"><span>#${Number(task.order)}</span><span>${escapeHtml(task.rel)}::${Number(task.id)}</span></div>
        <div class="taskItemMeta">${escapeHtml(task.category)} / ${escapeHtml(task.target_task)} / ${escapeHtml(task.source)}</div>
        <div class="miniBadges">${badges}</div>
        ${candidateBadges}
        ${wrongRenderBadges}
        ${auditBadges}
        ${yzrBadges}
      </button>`;
  }).join("") || `<div class="empty">No tasks match the filters.</div>`;
  els.taskList.querySelectorAll("[data-key]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedKey = button.dataset.key;
      renderTaskList();
      renderSelected();
    });
  });
}

function shortModel(id) {
  if (id.startsWith("gemini")) return "Gemini";
  if (id.includes("32b")) return "Qwen32B";
  if (id.includes("8b")) return "Qwen8B";
  return id;
}

function auditClass(grade) {
  if (grade === "STRONG") return "auditStrong";
  if (grade === "MID") return "auditMid";
  if (grade === "WRONG_RENDER_DIAGNOSTIC") return "auditDiagnostic";
  return "";
}

function selectedTask() {
  return state.tasks.find((task) => task.key === state.selectedKey);
}

async function loadSample(task) {
  if (!state.dataCache.has(task.path)) state.dataCache.set(task.path, fetchJson(`../${task.path}`));
  const rows = await state.dataCache.get(task.path);
  return rows[Number(task.id)];
}

function sampleQuestion(sample) {
  return sample?.question || sample?.modified_question || sample?.problem || sample?.query || sample?.prompt || "";
}

function sampleAnswer(sample) {
  return sample?.answer || sample?.modified_answer || sample?.ground_truth || sample?.gt_answer || sample?.target || "";
}

function sampleImageUrl(task, sample) {
  if (!task || !sample?.image_path) return "";
  const base = task.path.replace(/\/data\.json$/, "");
  return `../${base}/${sample.image_path}`.replaceAll("\\", "/");
}

async function renderSelected() {
  const task = selectedTask();
  if (!task) {
    els.taskHeader.innerHTML = `<div class="empty">No task selected.</div>`;
    els.questionText.textContent = "";
    els.sourceGrid.innerHTML = "";
    els.originalImageWrap.innerHTML = "";
    els.modelPanels.innerHTML = "";
    return;
  }
  const headerModels = isYzrMode()
    ? MODELS.filter((model) => yzrModelsForTask(task).has(model.id))
    : MODELS.slice(0, 3);
  const yzrHeaderBadges = isYzrMode()
    ? yzrRowsForTask(task).map((row) => `<span class="badge auditDiagnostic">YZR #${escapeHtml(row.case_index)} ${escapeHtml(shortModel(row.model))} ${escapeHtml(row.stratum)}${row.stratum_match ? "" : " supplement"}</span>`).join("")
    : "";
  els.taskHeader.innerHTML = `
    <div class="headerLine">
      <div>
        <h2 class="taskTitle">#${Number(task.order)} ${escapeHtml(task.rel)}::${Number(task.id)}</h2>
        <div class="taskSub">${escapeHtml(task.category)} / ${escapeHtml(task.target_task)} / ${escapeHtml(task.source)}</div>
      </div>
      <div class="miniBadges">${headerModels.map((model) => answerBadge("full", model, task.key)).join("")}${yzrHeaderBadges}</div>
    </div>`;

  els.questionText.textContent = "Loading prompt...";
  els.modelPanels.innerHTML = `<div class="empty">Loading trajectories...</div>`;
  try {
    const sample = await loadSample(task);
    const question = sampleQuestion(sample);
    const answer = sampleAnswer(sample);
    els.questionText.textContent = question || "(question not found)";
    els.sourceGrid.innerHTML = sourceCells(task, sample, answer);
    const src = sampleImageUrl(task, sample);
    els.originalImageWrap.innerHTML = src ? `<img src="${src}" alt="Original image" data-expand="${src}">` : `<div class="empty">No source image.</div>`;
    bindExpandableImages(els.originalImageWrap);
  } catch (err) {
    els.questionText.innerHTML = `<span class="error">${escapeHtml(err.message)}</span>`;
  }
  renderAllPanels(task);
}

function answerBadge(settingId, model, key) {
  const row = state.answers.get(runKey(settingId, model.id))?.get(key);
  if (!row) return `<span class="badge warn">${escapeHtml(model.label)} answer ?</span>`;
  return `<span class="badge ${row.correct ? "good" : "bad"}">${escapeHtml(model.label)} ${row.correct ? "correct" : "wrong"}</span>`;
}

function sourceCells(task, sample, answer) {
  const cells = [
    ["Task key", task.key],
    ["Data path", task.path],
    ["Image path", sample?.image_path || ""],
    ["Ground truth", answer || ""],
  ];
  return cells.map(([k, v]) => `<div class="sourceCell"><span>${escapeHtml(k)}</span><code>${escapeHtml(v)}</code></div>`).join("");
}

async function renderAllPanels(task) {
  const settings = isYzrMode()
    ? SETTINGS.filter((s) => s.id === "full" && state.enabledSettings.has(s.id))
    : SETTINGS.filter((s) => state.enabledSettings.has(s.id));
  const settingBlocks = settings.map((setting) => renderSettingBlock(setting, task));
  const html = await Promise.all(settingBlocks);
  els.modelPanels.innerHTML = html.join("") || `<div class="empty">No setting selected.</div>`;
  bindExpandableImages(els.modelPanels);
}

async function renderSettingBlock(setting, task) {
  const allowedYzrModels = isYzrMode() ? yzrModelsForTask(task) : null;
  const modelCards = MODELS
    .filter((m) => state.enabledModels.has(m.id))
    .filter((m) => !allowedYzrModels || allowedYzrModels.has(m.id))
    .map((model) => renderModelPanel(setting, model, task));
  const cards = await Promise.all(modelCards);
  const prompt = state.promptTemplates.get(setting.id) || "";
  return `
    <section class="settingBlock">
      <div class="settingTitle">${escapeHtml(setting.label)} <span class="badge">${escapeHtml(setting.id)}</span></div>
      <details>
        <summary>Prompt template: ${escapeHtml(setting.promptUrl.replace("../", ""))}</summary>
        <div class="markdown"><pre><code>${escapeHtml(prompt.trim())}</code></pre></div>
      </details>
      ${cards.join("") || `<div class="empty">No model selected.</div>`}
    </section>`;
}

async function renderModelPanel(setting, model, task) {
  const key = task.key;
  const rk = runKey(setting.id, model.id);
  const processRow = state.process.get(rk)?.get(key);
  const keyStepRow = state.keySteps.get(rk)?.get(key);
  const answerRow = state.answers.get(rk)?.get(key);
  const yzrRow = setting.id === "full" ? yzrRowForTaskModel(task, model.id) : null;
  const dir = outputDir(setting, model, task);
  try {
    const [qmd, steps] = await Promise.all([
      fetchText(`${dir}/q.md`).catch(() => ""),
      fetchText(`${dir}/steps.md`),
    ]);
    const imageRefs = await discoverImages(dir, collectImages(qmd, steps));
    return `
      <article class="modelCard">
        <div class="modelCardHeader">
          <div>
            <div class="modelName">${escapeHtml(model.label)}</div>
            <div class="scoreRow">${scoreBadges(processRow, answerRow, keyStepRow)}</div>
          </div>
          <div class="miniBadges">
            ${yzrRow ? `<span class="badge auditDiagnostic">ANNOTATE YZR #${escapeHtml(yzrRow.case_index)} ${escapeHtml(yzrRow.task_group)} ${escapeHtml(yzrRow.stratum)}${yzrRow.stratum_match ? "" : " supplement"}</span>` : ""}
            <span class="badge">${escapeHtml(dir.replace("../", ""))}</span>
          </div>
        </div>
        ${renderFullAuditPanel(setting, model, task)}
        ${renderJudgePanel(setting, processRow, keyStepRow)}
        ${renderAnnotationPanel(setting, model, task, processRow, keyStepRow)}
        <div class="modelBody">
          <div class="renderRail">
            <div class="panelTitle">Images</div>
            <div class="thumbGrid">${imageRefs.map((img) => thumbHtml(dir, img)).join("")}</div>
          </div>
          <div class="stepsArea">
            <details>
              <summary>Prompt file q.md</summary>
              <div class="markdown">${renderMarkdownLite(qmd, dir)}</div>
            </details>
            ${renderStepDetails(steps, dir)}
          </div>
        </div>
      </article>`;
  } catch (err) {
    return `
      <article class="modelCard">
        <div class="modelCardHeader">
          <div>
            <div class="modelName">${escapeHtml(model.label)}</div>
            <div class="scoreRow"><span class="badge warn">not available in this setting/task</span></div>
          </div>
          <div class="badge">${escapeHtml(dir.replace("../", ""))}</div>
        </div>
        <div class="empty">No trajectory files found here.</div>
      </article>`;
  }
}

function renderFullAuditPanel(setting, model, task) {
  if (setting.id !== "full") return "";
  if (isYzrMode()) return "";
  const row = auditRowForTaskModel(task, model.id);
  if (!row) return "";
  const scores = row.scores || {};
  const tags = row.exclusion_tags || [];
  const concerns = row.manual_review_concerns || [];
  return `
    <details class="auditPanel ${auditClass(row.grade)}" ${row.grade === "STRONG" || row.grade === "MID" ? "open" : ""}>
      <summary>
        <span>Strong Full audit</span>
        <span class="badge audit ${auditClass(row.grade)}">${escapeHtml(row.grade)} ${row.total_score}/14</span>
      </summary>
      <div class="auditGrid">
        <div><span>Original difficulty</span><strong>${scores.A_original_visual_difficulty ?? "n/a"}</strong></div>
        <div><span>Action specificity</span><strong>${scores.B_action_specificity ?? "n/a"}</strong></div>
        <div><span>Render correctness</span><strong>${scores.C_render_correctness ?? "n/a"}</strong></div>
        <div><span>Novel evidence</span><strong>${scores.D_novel_visual_evidence ?? "n/a"}</strong></div>
        <div><span>Consumption</span><strong>${scores.E_downstream_visual_consumption ?? "n/a"}</strong></div>
        <div><span>Reasoning impact</span><strong>${scores.F_reasoning_impact ?? "n/a"}</strong></div>
      </div>
      <div class="auditEvidence">
        <p><strong>Why:</strong> ${escapeHtml(row.why_possible_strong || "")}</p>
        <p><strong>Rendered evidence:</strong> ${escapeHtml(row.new_visual_evidence_summary || "")}</p>
        <p><strong>Consumption sentence:</strong> ${escapeHtml(row.consumption_sentence || "not detected")}</p>
        <p><strong>Counterfactual:</strong> ${escapeHtml(row.delete_render_counterfactual || "")}</p>
        ${tags.length ? `<p><strong>Tags:</strong> ${tags.map((tag) => `<span class="badge">${escapeHtml(tag)}</span>`).join(" ")}</p>` : ""}
        ${concerns.length ? `<p><strong>Manual review:</strong> ${escapeHtml(concerns.join("; "))}</p>` : ""}
      </div>
    </details>`;
}

function renderJudgePanel(setting, processRow, keyStepRow) {
  if (setting.id !== "full") return "";
  const judge = processRow?.judge || {};
  const keyText = keyStepRow
    ? (keyStepRow.no_valid_visual_step ? "No valid visual step" : `Step ${(keyStepRow.key_steps || []).join(", ") || "not selected"}`)
    : "not judged";
  return `
    <details class="judgePanel" open>
      <summary>Judge decision</summary>
      <div class="judgeDecisionGrid">
        <div>
          <span>Key visual step</span>
          <strong>${escapeHtml(keyText)}</strong>
          ${keyStepRow?.reason ? `<p>${escapeHtml(keyStepRow.reason)}</p>` : ""}
        </div>
        ${["action_relevance", "render_faithfulness", "feedback_uptake"].map((metric) => {
          const item = judge[metric];
          return `
            <div>
              <span>${escapeHtml(metric.replaceAll("_", " "))}</span>
              <strong>${judgeLevel(item)}</strong>
              ${item?.reason ? `<p>${escapeHtml(item.reason)}</p>` : ""}
            </div>`;
        }).join("")}
      </div>
      ${judge.summary ? `<div class="judgeSummary">${escapeHtml(judge.summary)}</div>` : ""}
    </details>`;
}

function judgeLevel(item) {
  const score = item?.score;
  if (score === 2 || item?.normalized_score === 1) return "high";
  if (score === 1 || item?.normalized_score === 0.5) return "partial";
  if (score === 0 || item?.normalized_score === 0) return "low";
  return "not judged";
}

function renderAnnotationPanel(setting, model, task, processRow, keyStepRow) {
  if (setting.id !== "full") return "";
  const ann = getAnnotation(task.key, setting.id, model.id);
  const judge = processRow?.judge || {};
  const yzrRow = yzrRowForTaskModel(task, model.id);
  const keyText = keyStepRow
    ? (keyStepRow.no_valid_visual_step ? "No valid visual step" : `Step ${(keyStepRow.key_steps || []).join(", ") || "not selected"}`)
    : "not judged";
  const judgeHint = [
    ["key_step_selection", "Key step", keyText],
    ["action_relevance", "Action"],
    ["render_faithfulness", "Render"],
    ["feedback_uptake", "Uptake"],
  ].map(([metric, label, preset]) => {
    if (preset) return `${label}: ${preset}`;
    const value = judge[metric]?.normalized_score;
    return `${label}: ${value ?? "n/a"}`;
  }).join(" | ");
  const yzrHint = yzrRow
    ? `YZR #${yzrRow.case_index} | ${yzrRow.task_group} | ${yzrRow.stratum} | stratum_match=${yzrRow.stratum_match}`
    : "";

  return `
    <details class="annotationPanel" open data-annotation-root data-task-key="${escapeHtml(task.key)}" data-setting="${escapeHtml(setting.id)}" data-model="${escapeHtml(model.id)}">
      <summary>
        Human annotation${yzrRow ? ` - YZR #${escapeHtml(yzrRow.case_index)}` : ""}
        <span class="annotationSaved"></span>
      </summary>
      <div class="annotationHint">
        Judge whether each LLM-judge decision is reasonable. Use three labels: Reasonable, Partially reasonable, or Unreasonable. ${escapeHtml([yzrHint, judgeHint].filter(Boolean).join(" | "))}
      </div>
      <div class="annotationGrid">
        ${ANNOTATION_FIELDS.map((field) => annotationFieldHtml(field, ann[field.id], task.key, setting.id, model.id)).join("")}
      </div>
      <div class="annotationNotes">
        <label>
          Note
          <textarea data-annotation-text="note" rows="2" placeholder="Optional reason or disagreement note">${escapeHtml(ann.note || "")}</textarea>
        </label>
      </div>
    </details>`;
}

function annotationFieldHtml(field, current, taskKeyValue, settingId, modelId) {
  const name = `ann-${settingId}-${modelId}-${taskKeyValue}-${field.id}`.replace(/[^a-zA-Z0-9_-]/g, "_");
  return `
    <div class="annotationField">
      <div class="annotationFieldTop">
        <strong>${escapeHtml(field.label)}</strong>
        <span>${escapeHtml(field.help)}</span>
      </div>
      <div class="annotationChoices">
        ${ANNOTATION_VALUES.map((value) => `
          <label class="choicePill ${current === value.id ? "selected" : ""}">
            <input
              type="radio"
              name="${escapeHtml(name)}"
              value="${escapeHtml(value.id)}"
              data-annotation-field="${escapeHtml(field.id)}"
              ${current === value.id ? "checked" : ""}
            />
            ${escapeHtml(value.label)}
          </label>`).join("")}
      </div>
    </div>`;
}

function scoreBadges(processRow, answerRow, keyStepRow) {
  const out = [];
  if (answerRow) out.push(`<span class="badge ${answerRow.correct ? "good" : "bad"}">ACC ${answerRow.correct ? "correct" : "wrong"}</span>`);
  else out.push(`<span class="badge warn">ACC not judged</span>`);
  if (keyStepRow) {
    const keyText = keyStepRow.no_valid_visual_step ? "no visual step" : `step ${(keyStepRow.key_steps || []).join(",") || "?"}`;
    out.push(`<span class="badge">key ${escapeHtml(keyText)}</span>`);
  } else {
    out.push(`<span class="badge warn">key step not judged</span>`);
  }
  const judge = processRow?.judge || {};
  for (const metric of ["action_relevance", "render_faithfulness", "feedback_uptake"]) {
    const value = judge[metric]?.normalized_score;
    out.push(`<span class="badge">${metric.replaceAll("_", " ")} ${value ?? "not judged"}</span>`);
  }
  if (judge.overall_failure_source) {
    out.push(`<span class="badge ${judge.overall_failure_source === "none" ? "good" : "warn"}">failure ${escapeHtml(judge.overall_failure_source)}</span>`);
  }
  return out.join("");
}

function collectImages(...texts) {
  const refs = new Set(["p0.png"]);
  for (const text of texts) {
    for (const match of String(text || "").matchAll(/!\[[^\]]*\]\(([^)]+\.png)\)/gi)) refs.add(match[1]);
  }
  return [...refs].sort((a, b) => imageNumber(a) - imageNumber(b));
}

async function imageExists(url) {
  try {
    const res = await fetch(url, { method: "HEAD", cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

async function discoverImages(dir, markdownRefs) {
  const refs = new Set(markdownRefs);
  const checks = [];
  for (let i = 0; i <= MAX_RENDER_INDEX; i += 1) {
    const name = `p${i}.png`;
    checks.push(imageExists(`${dir}/${name}`).then((ok) => {
      if (ok) refs.add(name);
    }));
  }
  await Promise.all(checks);
  return [...refs].sort((a, b) => imageNumber(a) - imageNumber(b));
}

function imageNumber(name) {
  const m = String(name).match(/p(\d+)\.png/i);
  return m ? Number(m[1]) : 9999;
}

function thumbHtml(dir, img) {
  const src = resolveImageUrl(img, dir);
  return `<div class="thumb"><div class="thumbLabel">${escapeHtml(img)}</div><img src="${escapeHtml(src)}" alt="${escapeHtml(img)}" data-expand="${escapeHtml(src)}" loading="lazy"></div>`;
}

function renderStepDetails(steps, dir) {
  const chunks = splitSteps(steps);
  if (!chunks.length) return `<details open><summary>steps.md</summary><div class="markdown">${renderMarkdownLite(steps, dir)}</div></details>`;
  return chunks.map((chunk, idx) => `
    <details ${idx === 0 ? "open" : ""}>
      <summary>${escapeHtml(chunk.title)}</summary>
      <div class="markdown">${renderMarkdownLite(chunk.body, dir)}</div>
    </details>`).join("");
}

function splitSteps(text) {
  const src = String(text || "").replace(/^\s*\*\*\s*$/gm, "").trim();
  const re = /(?:^|\r?\n)\s*(?:\*\*)?((?:Step\s+\d+\s+\((?:Text|Action Description)\)|Final Answer):)(?:\*\*)?/gi;
  const matches = [...src.matchAll(re)];
  if (!matches.length) return [];
  return matches.map((match, idx) => {
    const start = match.index + match[0].length;
    const end = idx + 1 < matches.length ? matches[idx + 1].index : src.length;
    const title = match[1].replace(/:$/, "");
    const body = src.slice(start, end).trim();
    return { title, body };
  }).filter((chunk) => chunk.body && chunk.body !== "**");
}

function encodeCodeBlock(code) {
  return btoa(unescape(encodeURIComponent(code)));
}

function decodeCodeBlock(encoded) {
  return decodeURIComponent(escape(atob(encoded)));
}

function renderMarkdownLite(text, baseDir) {
  let src = String(text || "");
  src = src.replace(/```(?:json|python)?\s*([\s\S]*?)```/gi, (_, code) => `@@CODE${encodeCodeBlock(code)}@@`);
  src = escapeHtml(src);
  src = src.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, href) => {
    const url = resolveImageUrl(href, baseDir);
    return `<img src="${escapeHtml(url)}" alt="${escapeHtml(alt || href)}" data-expand="${escapeHtml(url)}" loading="lazy">`;
  });
  src = src.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  src = src.replace(/@@CODE([A-Za-z0-9+/=]+)@@/g, (_, encoded) => `<pre><code>${escapeHtml(decodeCodeBlock(encoded).trim())}</code></pre>`);
  return src;
}

function resolveImageUrl(href, baseDir) {
  const raw = String(href || "").trim();
  if (!raw) return "";
  if (/^(?:https?:|data:|blob:)/i.test(raw)) return raw;
  if (raw.startsWith("../") || raw.startsWith("./") || raw.startsWith("/")) return raw;
  if (raw.startsWith("final_results/") || raw.startsWith("annotation/") || raw.startsWith("newtasks/") || raw.startsWith("neweval/")) {
    return `../${raw}`;
  }
  return `${baseDir}/${raw}`;
}

function bindExpandableImages(root) {
  root.querySelectorAll("[data-expand]").forEach((img) => {
    img.addEventListener("error", () => markMissingImage(img));
    if (img.complete && img.naturalWidth === 0) markMissingImage(img);
    img.addEventListener("click", () => {
      if (img.dataset.missing === "1") return;
      openModal(img.dataset.expand);
    });
  });
}

function markMissingImage(img) {
  img.dataset.missing = "1";
  img.title = `Missing image: ${img.currentSrc || img.src || img.dataset.expand || ""}`;
  img.closest(".thumb")?.classList.add("missingImage");
}

function openModal(src) {
  if (!src) return;
  els.modalImage.style.display = "none";
  els.imageModal.dataset.error = "";
  els.modalImage.onload = () => {
    els.modalImage.style.display = "";
    els.imageModal.dataset.error = "";
  };
  els.modalImage.onerror = () => {
    els.modalImage.style.display = "none";
    els.imageModal.dataset.error = `Image not found: ${src}`;
  };
  els.modalImage.src = src;
  els.imageModal.hidden = false;
}

function closeModal() {
  els.imageModal.hidden = true;
  els.imageModal.dataset.error = "";
  els.modalImage.onload = null;
  els.modalImage.onerror = null;
  els.modalImage.style.display = "";
  els.modalImage.src = "";
}

loadAll().catch((err) => {
  console.error(err);
  els.loadStatus.textContent = "Load failed";
  els.taskHeader.innerHTML = `<div class="error">${escapeHtml(err.message)}</div>`;
});
