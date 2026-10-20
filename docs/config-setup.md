# 模型配置填写说明

## 1. 配置文件在哪

- 模板：[`config/reviewer.example.toml`](../config/reviewer.example.toml)
- 本机实际配置：[`config/reviewer.toml`](../config/reviewer.toml)
- `config/reviewer.toml` 已加入 `.gitignore`，不会误提交到 GitHub。

如果以后在新机器上开始工作：

```powershell
Copy-Item .\config\reviewer.example.toml .\config\reviewer.toml
```

## 2. 千问 Key 填写

只修改本机 `config/reviewer.toml`：

```toml
[providers.qwen]
enabled = true
api_key = "在这里填写千问 AI 平台 API Key"
```

需要确认该 Key 所属业务空间已开通以下模型：

- `qwen3.8-max-0902`
- `gui-plus-2026-02-26`
- `qwen3.5-ocr`
- `qwen3.7-text-embedding`
- `qwen3.7-text-rerank`
- `qwen3-vl-embedding`
- `qwen3-vl-rerank`

如果某个模型不可用，引擎应明确记录 `model_unavailable`，不能静默换成通用模型并把结果当成同等质量结果。

## 3. DeepSeek 作为备用

```toml
[providers.deepseek]
enabled = true
api_key = "在这里填写 DeepSeek API Key"
```

DeepSeek 主要用于备用推理或多模型复核。专用 UI 定位仍优先使用 GUI-Plus/Holo 系列，避免用通用文本模型猜测界面元素位置。

## 4. 不要做的事

- 不要把 Key 写入 Python、Markdown、`.env.example` 或提交记录。
- 不要在截图、日志、错误堆栈中打印完整 Key。
- 不要把 `config/reviewer.toml` 发给外部模型服务。
- 不要在未记录供应商和模型版本时比较不同模型的结果。

## 5. 运行依赖

基础服务：

```powershell
python -m pip install -r requirements.txt
```

开发和测试：

```powershell
python -m pip install -r requirements-dev.txt
```

可选本地 UI 感知实验：

```powershell
python -m pip install -r requirements-perception.txt
```

本地 PyTorch 路径必须使用 64 位 Python 3.11+。当前项目默认使用云端感知模型，不要求本机安装 PyTorch。

## 6. 5070 Ti 本地模型

目标机器按 RTX 5070 Ti、16 GB 显存配置。建议使用 Python 3.12 64 位，并创建独立虚拟环境：

```powershell
py -3.12 -m venv .venv-5070ti
.\.venv-5070ti\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-perception.txt
```

在同一份本地 `config/reviewer.toml` 中启用一个本地感知模型：

```toml
[models.local_holo15]
enabled = true
model_id = "Hcompany/Holo1.5-7B"
device = "cuda"
dtype = "auto"
load_in_4bit = true
```

运行：

```powershell
python -m engine review .\屏幕截图.png --provider local_holo
```

如果需要比较开源模型的游戏界面定位能力，将第一项禁用、启用
`models.local_ui_tars`，再以 `--provider local_ui_tars` 运行。

说明：

- 7B BF16 通常无法安全装入 16 GB 显存，因此默认启用 NF4 4-bit。
- 首次运行会下载模型权重，下载位置由 Hugging Face 缓存配置决定。
- 本地模型后端是惰性加载，不调用本地模型时不会导入 PyTorch。
- 当前机器仍是 32 位 Python 与 6 GB GPU，因此默认保持云端。
- 建议 5070 Ti 只承担 UI localization/OCR/视觉感知；综合解释仍可调用云端 `qwen3.8-max-0902`，形成本地感知 + 云端推理。

## 7. 配置验收

配置完成后运行：

```powershell
python -m engine validate-config
python -m engine health
```

这两条命令会检查配置文件语法、Key 是否存在、模型名是否已填写，但不会输出 Key 内容或发起收费调用。
