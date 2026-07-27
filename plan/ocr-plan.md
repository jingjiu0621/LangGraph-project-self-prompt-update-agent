# OCR / VLM 视觉录入 — 执行计划

> 文档定位：给后续执行 AI（我自己或其他人）的实现参考。  
> 触发条件：README.md 已记录架构决策，本文件展开具体实现步骤。  
> 当前状态：设计阶段，未编码。

---

## 1. 一句话目标

在现有文本/Markdown 导入基础上，增加**图片和 PDF 文件上传 → VLM 视觉模型端到端提取 → 结构化 JSON → 入库**的能力。

---

## 2. 架构概览

```text
用户上传图片/PDF
        │
        ▼
POST /api/intake/ocr-upload   →  暂存文件，返回 session_id
        │
        ▼
POST /api/intake/ocr-confirm  →  调 VLM API → 结构化 JSON
        │                           （模式 1：纯 VLM 端到端）
        ▼
packages/clinical_intake/ocr.py
  → 构建 prompt + 图片 → 调用模型网关
  → 解析 Structured Output JSON
  → 脱敏 → 走 normalize_payload_results + _write_db_batch 入库
        │
        ▼
  返回入库结果
```

### 为什么两段式

| 步骤 | 目的 |
|------|------|
| ocr-upload | 上传文件 + 展示脱敏预览（零模型成本） |
| ocr-confirm | 用户确认后调模型（产生 API 费用） |

避免用户误操作浪费模型调用成本，同时给用户机会在调模型前确认内容。

---

## 3. 接口设计

### 3.1 POST /api/intake/ocr-upload

上传文件，暂存到 `data/uploads/`，返回 `session_id`。

**Request**: `multipart/form-data`
- `file`: 图片（PNG/JPG）或 PDF

**Response** (200):
```json
{
  "session_id": "upload_a1b2c3d4",
  "filename": "report.png",
  "file_size_bytes": 245678,
  "mime_type": "image/png",
  "preview": {
    "page_count": 1,
    "has_text": true
  }
}
```

**Error** (400):
```json
{
  "error": "unsupported_format",
  "message": "仅支持 PNG、JPG、PDF 格式"
}
```

### 3.2 POST /api/intake/ocr-confirm

用户确认后，对暂存文件执行 VLM 提取。

**Request**: `application/json`
```json
{
  "session_id": "upload_a1b2c3d4",
  "patient_id": "patient_a_001",
  "measured_at": "2026-07-18",
  "source_name": "report-20260718.png"
}
```

**Response** (200):
```json
{
  "document_id": "doc_abc123",
  "lab_results_count": 8,
  "imaging_findings_count": 0,
  "privacy_findings_count": 0,
  "model": "claude-sonnet-4-20250514",
  "usage": {
    "input_tokens": 12450,
    "output_tokens": 850
  }
}
```

**Error** (404): `session_id` 不存在或已过期  
**Error** (502): 模型 API 调用失败

### 3.3 文件清理

- 上传文件保留 30 分钟后自动清理（cron 或延迟任务）
- `ocr-confirm` 调用成功后立即清理该文件
- 文件存于 `data/uploads/{session_id}/`

---

## 4. 模块设计: `packages/clinical_intake/ocr.py`

### 4.1 核心函数

```python
def process_image_file(
    image_bytes: bytes,
    mime_type: str,                # "image/png" | "image/jpeg" | "application/pdf"
    patient_id: str,
    source_name: str,
    measured_at: str | None = None,
) -> dict:
    """主入口：VLM 提取 → 脱敏 → 入库 → 返回结果"""
```

### 4.2 内部步骤

```python
def _build_vision_prompt() -> str:
    """构建带 JSON Schema 约束的系统提示"""

def _call_vlm(image_bytes: bytes, mime_type: str) -> dict:
    """调模型网关，传入图片 + prompt，返回结构化 JSON"""

def _validate_vlm_output(data: dict) -> dict:
    """校验模型返回的 JSON 结构和必填字段"""

def _fallback_parse(raw: str) -> dict | None:
    """模型未输出合法 JSON 时的文本解析兜底（可选）"""
```

### 4.3 JSON Schema（VLM Structured Output 约束）

```json
{
  "type": "object",
  "properties": {
    "patient": {
      "type": "object",
      "properties": {
        "display_name": {"type": "string"},
        "sex": {"type": "string"},
        "age": {"type": "integer"}
      }
    },
    "records": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "form_id": {"type": "string"},
          "time_key": {"type": "string"},
          "measured_at": {"type": "string"},
          "results": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": {"type": "string"},
                "value": {"type": "number"},
                "unit": {"type": "string"},
                "normal_low": {"type": "number"},
                "normal_high": {"type": "number"}
              },
              "required": ["name", "value", "unit", "normal_low", "normal_high"]
            }
          },
          "imaging_findings": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"}
              }
            }
          }
        },
        "required": ["results"]
      }
    }
  },
  "required": ["records"]
}
```

这个 Schema 与现有 `normalize_payload_results` 的输入格式兼容。

---

## 5. VLM Prompt 设计

### 5.1 System Prompt

```text
你是一个医疗检查报告结构化提取助手。
你的任务是将化验单/检查报告中的内容提取为结构化 JSON。

提取规则：
1. 报告中的患者姓名、手机号、身份证号原文保留（后续有独立脱敏步骤）。
2. 每个检查项目必须包含：指标名称(name)、数值(value)、单位(unit)、正常下限(normal_low)、正常上限(normal_high)。
3. 数值保持原样，不要做单位换算。
4. 如果一项检查有多个子项（如血常规），每行都是一个独立结果。
5. 参考范围可能有各种格式（"3.5-5.5"、"3.5~5.5"、"3.5-5.5 ×10^9/L"等），需要正确提取上下限数值。
6. 日期/阶段标记按报告上的实际日期提取。
7. 如果有影像检查所见，提取到 imaging_findings 中。
8. 如果报告上没有患者姓名，display_name 用匿名占位。

输出必须严格遵循提供的 JSON Schema。
```

### 5.2 User Message

```
请提取这份检查报告中的所有检查项目。
```

（图片通过视觉模态传入）

---

## 6. 前端修改

### 6.1 文件上传区

在底部数据导入区域新增：

```html
<div id="ocr-upload-area">
  <input type="file" accept="image/png,image/jpeg,application/pdf" />
  <button id="btn-ocr-upload">上传并预览</button>
  <div id="ocr-preview"></div>
  <button id="btn-ocr-confirm" disabled>确认并提取入库</button>
</div>
```

### 6.2 交互流程

```
选择文件 → 点击"上传并预览"
  → POST /api/intake/ocr-upload
  → 展示文件预览 + 脱敏后文本预览
  → 用户确认 → 点击"确认并提取入库"
  → POST /api/intake/ocr-confirm
  → 展示入库结果（指标数、图片数）
```

### 6.3 JS 函数

```javascript
async function uploadOcrFile(file) { ... }
async function confirmOcrExtract(sessionId, patientId) { ... }
```

---

## 7. 后端实现步骤

### Step 1: 文件存储工具

在 `packages/clinical_intake/ocr.py` 中添加文件管理：

```python
_UPLOAD_DIR = ROOT / "data" / "uploads"

def _save_upload(file_bytes: bytes, suffix: str) -> str:
    """保存上传文件，返回 session_id"""
    session_id = "upload_" + uuid.uuid4().hex[:12]
    session_dir = _UPLOAD_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / f"file{suffix}").write_bytes(file_bytes)
    return session_id

def _get_upload(session_id: str) -> tuple[bytes, str] | None:
    """读取暂存文件，返回 (bytes, suffix)"""
    session_dir = _UPLOAD_DIR / session_id
    if not session_dir.exists():
        return None
    for f in session_dir.iterdir():
        return f.read_bytes(), f.suffix
    return None

def _clean_upload(session_id: str) -> None:
    """清理暂存文件"""
    import shutil
    shutil.rmtree(_UPLOAD_DIR / session_id, ignore_errors=True)
```

### Step 2: 模型网关扩展

当前 `ModelGateway.complete(prompt)` 只处理文本。需要新增视觉方法：

**选项 A**：在 `model_gateway.py` 新增 `complete_vision()`

```python
def complete_vision(self, prompt: str, image_bytes: bytes, mime_type: str) -> ModelResult:
    """传入图片 + prompt，调用支持 vision 的模型 API"""
```

**选项 B**：新建 `packages/clinical_agent/vision_gateway.py`

建议选 **A**，保持统一网关入口，避免两个网关各自维护一套 API key 逻辑。

Vision API 调用格式（以 Anthropic Claude API 为例）：

```python
payload = {
    "model": self.model_name,
    "max_tokens": 4096,
    "messages": [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": base64.b64encode(image_bytes).decode()
                }
            }
        ]
    }]
}
```

### Step 3: 核心处理函数

在 `ocr.py` 中实现 `process_image_file`：

```python
def process_image_file(
    image_bytes: bytes,
    mime_type: str,
    patient_id: str,
    source_name: str,
    measured_at: str | None = None,
) -> dict:
    # 1. 调 VLM
    prompt = _build_vision_prompt()
    result = ModelGateway().complete_vision(prompt, image_bytes, mime_type)
    if not result.persisted:
        return {"error": "model_call_failed", "message": result.text}

    # 2. 解析 JSON
    payload = json.loads(result.text)

    # 3. 标准化 + 脱敏 + 入库
    lab_results, imaging, patient = normalize_payload_results(payload)
    clean, findings = deidentify_text(json.dumps(payload, ensure_ascii=False))
    raw_text = json.dumps(payload, ensure_ascii=False)

    return _write_db_batch(
        patient_id, source_name, raw_text, clean, findings,
        lab_results, imaging, patient, measured_at or date.today().isoformat()
    )
```

### Step 4: 添加 API 路由

在 `apps/api/main.py` 中新增：

```python
@app.post("/api/intake/ocr-upload")
async def ocr_upload(file: UploadFile = File(...)):
    ...

@app.post("/api/intake/ocr-confirm")
def ocr_confirm(payload: dict = Body(...)):
    session_id = payload.get("session_id")
    ...
    result = process_image_file(...)
    _clean_upload(session_id)
    return result
```

### Step 5: 前端

在 `public/index.html` 和 `public/app.js` 中新增文件上传 UI 和交互逻辑。

---

## 8. 错误处理策略

| 失败场景 | 前端表现 | 后端行为 |
|----------|----------|----------|
| 文件格式不支持 | 弹窗提示 | 返回 400 |
| 文件过大（>20MB） | 弹窗提示 | 返回 413 |
| VLM API 调用失败 | 显示重试按钮 | 记录 trace，不清除暂存文件 |
| VLM 输出 JSON 格式错误 | 显示"提取失败，请重试" | 尝试文本兜底，仍失败则报错 |
| VLM 提取结果为空 | 显示"未识别到检查项目" | 返回空结果（不落库） |
| session_id 过期 | 提示重新上传 | 返回 404 |

---

## 9. 验证

### 9.1 单元测试

```python
# tests/test_ocr.py
def test_ocr_process_image_file():
    ...
def test_build_vision_prompt_contains_schema():
    ...
def test_validate_vlm_output_valid():
    ...
def test_validate_vlm_output_missing_fields():
    ...
def test_fallback_parse():
    ...
```

### 9.2 集成测试

```powershell
# 上传测试图片
curl -X POST http://127.0.0.1:8000/api/intake/ocr-upload ^
  -F "file=@test_data/lab_report.png"

# 确认提取
curl -X POST http://127.0.0.1:8000/api/intake/ocr-confirm ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"...\", \"patient_id\":\"test_patient\"}"
```

### 9.3 回归检查

```powershell
python -m compileall apps packages
python -m unittest tests.test_clinical_prototype
node --check public/app.js
```

---

## 10. 依赖

保持最小新增原则，以下都是现有依赖：

| 依赖 | 用途 | 当前状态 |
|------|------|----------|
| `urllib` | HTTP 请求（模型 API） | 已存在 |
| `uuid` | session_id / document_id | 已存在 |
| `base64` | 图片编码 | Python 标准库 |
| `fastapi.UploadFile` | 文件上传 | 已存在 |

暂不需要新增第三方包。

---

## 11. 与现有代码的集成点

```
apps/api/main.py                    ← 新增 2 个路由
  │
  ├─→ packages/clinical_intake/ocr.py         ← 新增文件
  │     ├─→ ModelGateway.complete_vision()     ← 扩展现有网关
  │     ├─→ normalize_payload_results()        ← 复用现有
  │     ├─→ deidentify_text()                  ← 复用现有
  │     └─→ _write_db_batch()                  ← 复用现有
  │
  └─→ public/index.html / app.js              ← 新增上传 UI
```

---

## 12. 后续扩展方向

| 阶段 | 升级点 | 触发条件 |
|------|--------|----------|
| 当前 | VLM 端到端（模式 1） | 初始实现 |
| 阶段 2 | 文件暂存 + 预览确认（两段式） | 用户体验优化 |
| 阶段 3 | PaddleOCR 文字检测 + 本地模型（模式 3） | 真实患者数据，合规要求本地 |
| 阶段 4 | 表格结构还原 + 多页 PDF 支持 | 复杂报告格式需求 |
| 阶段 5 | OCR 结果人工校对 UI | 生产部署 |
