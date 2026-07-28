# See2Think: Do Multimodal Models Really Use Intermediate Visual States?

<p align="center">
  Siyu Yan<sup>1,3,*</sup>&nbsp;&nbsp;
  Zhuoran Yan<sup>2,*</sup>&nbsp;&nbsp;
  Haiying Xu<sup>3,4,*</sup>&nbsp;&nbsp;
  Panhao Zhou<sup>2</sup>&nbsp;&nbsp;
  Jingyu Chen<sup>2</sup>&nbsp;&nbsp;
  Chenhao Ji<sup>3</sup>&nbsp;&nbsp;
  Shuo Cao<sup>3,5</sup>&nbsp;&nbsp;
  Yongheng Zhang<sup>2</sup>&nbsp;&nbsp;
  Haoze Liu<sup>3</sup>&nbsp;&nbsp;
  Siyu Zhang<sup>3,6</sup>&nbsp;&nbsp;
  Xiwen Gu<sup>7</sup>&nbsp;&nbsp;
  Yihao Liu<sup>3</sup>&nbsp;&nbsp;
  Alex Jinpeng Wang<sup>2,†</sup>
</p>

<p align="center">
  <sup>1</sup>The Hong Kong University of Science and Technology&nbsp;&nbsp;&nbsp;
  <sup>2</sup>Central South University&nbsp;&nbsp;&nbsp;
  <sup>3</sup>Shanghai AI Laboratory<br>
  <sup>4</sup>The Hong Kong University of Science and Technology (Guangzhou)&nbsp;&nbsp;&nbsp;
  <sup>5</sup>University of Science and Technology of China<br>
  <sup>6</sup>Fudan University&nbsp;&nbsp;&nbsp;
  <sup>7</sup>Wuhan University<br>
  <sup>*</sup>Equal contribution&nbsp;&nbsp;&nbsp;
  <sup>†</sup>Corresponding author
</p>

<p align="center">
  <a href="#"><img src="https://img.shields.io/badge/Paper-arXiv-red" alt="Paper"></a>
  <a href="https://sgysy.github.io/seetothink/"><img src="https://img.shields.io/badge/Project-Page-blue" alt="Project Page"></a>
  <a href="https://github.com/CSU-JPG/See2Think"><img src="https://img.shields.io/badge/Code-GitHub-black" alt="Code"></a>
  <img src="https://img.shields.io/badge/Python-3.9%2B-orange" alt="Python 3.9+">
</p>

<p align="center">
  <a href="https://sgysy.github.io/seetothink/">Project Page</a>
</p>

---

## Overview

**See2Think** evaluates whether multimodal models genuinely use intermediate visual states during reasoning, rather than merely producing visual-looking traces.

The framework contains two components:

- **See2ThinkBench**, a 1,200-sample open-ended benchmark spanning 12 task categories across 2D structured reasoning, 3D scene reasoning, and real-world visual reasoning.
- **Visual Action-of-Thought (VAoT)**, an inference protocol that records textual thoughts, visual actions, rendered visual states, subsequent reasoning, and final answers.

See2Think compares four controlled settings:

| Setting | Description |
| --- | --- |
| `CoT` | Text-only chain-of-thought baseline. |
| `VAoT-NoRender` | The model proposes visual actions, but no image is rendered back. |
| `VAoT-Full` | The model receives rendered visual states after visual actions. |
| `VAoT-WrongRender` | The model receives task-relevant corrupted visual feedback for diagnostic intervention. |

## Framework

```text
Input image + open-ended question
        |
        v
Textual thought
        |
        v
Structured visual action
        |
        v
Renderer -> intermediate visual state
        |
        v
Subsequent reasoning -> final answer
```

Process-level diagnosis evaluates three aspects of VAoT-Full trajectories:

| Metric | What it measures |
| --- | --- |
| Action Relevance | Whether the selected visual operation targets task-relevant evidence. |
| Render Faithfulness | Whether the renderer faithfully executes the requested visual action. |
| Feedback Uptake | Whether the model actually uses the rendered visual state in later reasoning. |

WrongRender diagnostics further test behavioral dependence by corrupting task-relevant visual evidence while keeping the reasoning model unaware of the corruption.

## Highlights

- **Unified open-ended benchmark:** 1,200 visually dependent problems across 12 task categories.
- **Controlled visual-state ablations:** CoT, VAoT-NoRender, VAoT-Full, and VAoT-WrongRender are evaluated on matched samples.
- **Process-level evaluation:** visual action quality, rendering quality, and feedback uptake are measured separately from final answer accuracy.
- **Corrupted-feedback diagnosis:** WrongRender probes whether models follow intermediate visual states even when those states are misleading.
- **Paper-ready analysis tools:** scripts generate grouped accuracy tables, process-score summaries, transition statistics, and RF/FU intervention tables.

## Repository layout

| Path | Purpose |
| --- | --- |
| `solve/` | Core inference pipeline, model clients, VAoT execution, and renderer integration. |
| `convert/` | Parsing and evaluation helper code. |
| `neweval/` | Answer judging and process-level judging pipeline. |
| `scripts/` | Experiment launchers, result assembly, paper-table generation, and audit tooling. |
| `viewer/` | Local trajectory viewer frontend. |
| `json/` | Lightweight task manifests and benchmark metadata. |
| `prompt/`, `newprompt/` | Prompt templates for the four inference settings and rendering/intervention steps. |
| `analysis/` | Audit criteria and small analysis notes. |
| `docs/` | Reproducibility and repository-release documentation. |
| `tests/` | Unit tests for maintained utilities. |

Large benchmark images, generated trajectories, rendered images, logs, audit packets, and paper-ready output bundles are intentionally excluded from git.

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/CSU-JPG/See2Think.git
cd See2Think
```

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configure local endpoints

Copy the example config and fill in your local API endpoints:

```bash
cp config.qwen.example.sh config.sh
source config.sh
```

`config.sh` is ignored by git and must never contain committed credentials.

Important variables:

```bash
export SEE2THINK_LLM_BACKEND="openai"      # openai | vllm
export OPENAI_API_KEY="..."
export OPENAI_BASE_URL="..."

export GEMINI_API_KEY="..."
export GEMINI_BASE_URL="..."

export SEE2THINK_DATA_BASE="/path/to/See2Think"
export SEE2THINK_OUTPUT_BASE="/path/to/outputs"
export SEE2THINK_LOG_DIR="/path/to/logs"
```

## Running Experiments

Run or resume one model/setting worker:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_remaining1200_one.ps1
```

Check experiment progress:

```bash
python scripts/check_experiment_status.py
```

Assemble completed 1,200-task results:

```bash
python scripts/assemble_all_1200_results.py
```

Run answer and process evaluation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_acc_and_eval_rerun.ps1
```

Generate paper-style tables:

```bash
python scripts/analyze_split_and_merged_1200.py
python scripts/export_merged_1200_evaluations.py
python scripts/export_paired_intervention_csvs_1200.py
```

## WrongRender Quality Audit

Build or inspect human-audit packets with:

```bash
python scripts/wrongrender_audit.py --help
```

Serve the local annotation frontend:

```bash
python scripts/wrongrender_audit.py serve --audit-dir audits/wrongrender_quality_90 --port 8765
```

Then open:

```text
http://127.0.0.1:8765
```

The audit UI is designed to judge image quality only. It does not require using model answers or post-WrongRender reasoning.

## Data and Results

This repository does not include full benchmark image folders or generated model outputs. For reproducibility, release large artifacts separately and keep only lightweight manifests in git.

Recommended release artifacts:

1. task manifests under `json/`;
2. benchmark source/version notes;
3. scripts for rebuilding trajectories and evaluations;
4. compact CSV/JSON summaries;
5. external archives or download links for raw images, rendered trajectories, and full result folders.

Ignored local/generated paths include:

```text
annotation/dataset/
newtasks/
newtasks_archive/
newtasks_reused/
final_results/
final_results_1200/
outputs/
exports/
deliverables/
audits/
logs/
newlogs/
neweval/results/
```

## Citation

If you find See2Think useful, please cite:

```bibtex
@article{yan2026see2think,
  title   = {See2Think: Do Multimodal Models Really Use Intermediate Visual States?},
  author  = {Yan, Siyu and Yan, Zhuoran and Xu, Haiying and Zhou, Panhao and Chen, Jingyu and Ji, Chenhao and Cao, Shuo and Zhang, Yongheng and Liu, Haoze and Zhang, Siyu and Gu, Xiwen and Liu, Yihao and Wang, Alex Jinpeng},
  journal = {arXiv preprint},
  year    = {2026}
}
```

## Acknowledgments

See2Think builds on open-source and public benchmark resources across diagrammatic reasoning, 3D scene reasoning, embodied manipulation, and real-world visual reasoning. Please also cite the original benchmark sources when using released See2Think task manifests.
