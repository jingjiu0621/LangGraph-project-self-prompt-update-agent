# OCR / 视觉录入模块 — 架构说明

> 文档定位：技术交接与开发人员项目认识。  
> 读者：接手 OCR 模块的开发者、评估方案的技术负责人。  
> 内容：设计背景、架构选择、模块职责、接口契约、迁移路径。

---

## 1. 设计背景

### 1.1 要解决什么问题

用户在 Phase 0-1 阶段通过手写 Markdown/JSON 导入检查数据，但真实场景下用户手里的检查报告是：

- 医院化验单照片（手机拍的）
- PDF 格式的检验报告
- 截图或扫描件

需要一个入口把这些**视觉格式的报告**转化为已有的结构化数据。

### 1.2 为什么不走传统 OCR

2025-2026 年医疗文档处理领域的主要趋势是 **VLM 直接取代传统 OCR**，而不是叠加使用：

- **John Snow Labs Schema-Constrained OCR**（2025）— 跳过"文字识别→结构化"两步，让模型直接按目标 Schema 输出
- **EACL 2026 论文** "Compact Multimodal Language Models as Robust OCR Alternatives for Noisy Textual Clinical Reports" — 紧凑 VLM 在噪声临床报告上已能替代传统 OCR
- **RAPTOR+（2025）** — 视觉语言框架实现端到端的临床文档理解

对于本项目，核心观察是：

| 对比维度 | 传统 OCR 管线（PaddleOCR/Tesseract） | VLM 端到端（Claude Vision） |
|----------|--------------------------------------|----------------------------|
| 医院化验单支持 | 需要版面分析 + 表格线识别，不同格式需调参 | 零配置，直接理解表格语义 |
| 中文支持 | 好（PaddleOCR） | 好 |
| 开发成本 | 高（安装、GPU、调参、容错） | 低（API 调用） |
| 运行时成本 | 本地运行，硬件成本 | API Token 成本 |
| 数据出域 | 本地，数据不出域 | 数据需过 API |
| 维护成本 | 格式变化需调规则 | 提示词微调即可 |

**结论**：Phase 1 使用合成数据，无合规顾虑，直接选 VLM 端到端。

---

## 2. 架构概览

### 2.1 在项目中的位置

```
┌─────────────────────────────────────────────────┐
│                  用户上传图片/PDF                  │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│          apps/api/main.py (FastAPI)             │
│  POST /api/intake/ocr-upload    (文件暂存)       │
│  POST /api/intake/ocr-confirm   (VLM 提取入库)   │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│     packages/clinical_intake/ocr.py             │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │build_    │→│_call_vlm │→│_validate_vlm  │  │
│  │vision_   │  │          │  │_output        │  │
│  │prompt    │  │          │  │               │  │
│  └──────────┘  └──────────┘  └───────┬───────┘  │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│     复用现有模块（零修改）                         │
│  ┌──────────────┐  ┌──────────┐  ┌───────────┐  │
│  │normalize_    │→│deidentify│→│_write_db_  │  │
│  │payload_      │  │_text     │  │batch      │  │
│  │results       │  │          │  │           │  │
│  └──────────────┘  └──────────┘  └───────────┘  │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│              SQLite (6 张表)                     │
└─────────────────────────────────────────────────┘
```

### 2.2 两段式 API 原因

```
ocr-upload (零成本)
  → 用户确认预览内容
  → ocr-confirm (产生 API 费用)
```

核心逻辑：**确认在前，调模型在后**。上传后用户可以查看文件是否被正确识别，确认后再花 Token 调模型。

---

## 3. 模块职责

### 3.1 `packages/clinical_intake/ocr.py` — 新增

| 函数 | 可见性 | 职责 |
|------|--------|------|
| `process_image_file()` | **公开** | 主入口：接收图片 → VLM → 入库 |
| `_build_vision_prompt()` | 内部 | 构建带 JSON Schema 约束的系统提示 |
| `_call_vlm()` | 内部 | 调 ModelGateway 传入图片 + prompt |
| `_validate_vlm_output()` | 内部 | 校验模型返回 JSON 的合法性 |
| `_save_upload()` | 内部 | 保存上传文件到 `data/uploads/` |
| `_get_upload()` | 内部 | 读取暂存文件 |
| `_clean_upload()` | 内部 | 清理暂存文件 |

### 3.2 `packages/clinical_agent/model_gateway.py` — 扩展

在现有 `complete()` 基础上新增 `complete_vision()`，支持图片输入。

### 3.3 `apps/api/main.py` — 新增路由

| 路由 | 方法 | 用途 |
|------|------|------|
| `POST /api/intake/ocr-upload` | `UploadFile` | 上传文件，返回 session_id |
| `POST /api/intake/ocr-confirm` | JSON Body | 确认提取，VLM 调用 + 入库 |

### 3.4 `public/` — 新增 UI

在底部数据导入区域新增文件上传面板。

---

## 4. 接口契约

### 4.1 文件上传

**Request**: `multipart/form-data`
- `file`: 图片或 PDF，最大 20MB

**支持的格式**:

| 格式 | MIME | 备注 |
|------|------|------|
| PNG | image/png | 首推，无损 |
| JPEG | image/jpeg | 广泛兼容 |
| PDF | application/pdf | 处理首页 |

**Response** (200):
```json
{
  "session_id": "upload_a1b2c3d4",
  "filename": "report.png",
  "file_size_bytes": 245678,
  "mime_type": "image/png"
}
```

### 4.2 VLM 提取确认

**Request**:
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
  "model": "claude-sonnet-4-20250514"
}
```

### 4.3 VLM 输出 Schema

与 `normalize_payload_results()` 的输入兼容：

```json
{
  "patient": { "display_name": "...", "sex": "男", "age": 45 },
  "records": [
    {
      "form_id": "ocr_20260718",
      "time_key": "1~2026-07-18",
      "measured_at": "2026-07-18",
      "results": [
        {
          "name": "白细胞计数(WBC)",
          "value": 10.2,
          "unit": "×10^9/L",
          "normal_low": 3.5,
          "normal_high": 9.5
        }
      ],
      "imaging_findings": []
    }
  ]
}
```

### 4.4 ModelGateway 扩展

```python
class ModelGateway:
    def complete(self, prompt: str) -> ModelResult:
        """现有文本模型调用"""

    def complete_vision(self, prompt: str, image_bytes: bytes, mime_type: str) -> ModelResult:
        """新增视觉模型调用：传入图片 + prompt，返回结构化 JSON 文本"""
```

---

## 5. 提示词设计要点

VLM 提示词的设计直接影响提取质量。以下是关键约束：

### 5.1 必须做的事

1. **强制 JSON Schema 输出** — 使用 API 的 Structured Output / JSON mode 约束
2. **明确提取粒度** — 化验单每个子项（如"白细胞计数"）是一条独立记录
3. **保留原始数值** — 不做单位换算、不做计算
4. **保留患者姓名** — 脱敏在入库前由隐私模块独立处理

### 5.2 常见陷阱

| 陷阱 | 表现 | 缓解 |
|------|------|------|
| 单位拆分 | "×10^9/L" 被识别为单独一行 | 提示词强调单位和指标名绑定 |
| 参考范围格式不一致 | "3.5-5.5" vs "3.5~5.5" | 提示词说明预期格式 |
| 合并单元格 | 表头跨列导致指标名缺失 | 提示词说明上下文推理 |
| 参考范围含文字 | "5.0-25.0 ↑" | 提示词要求提取纯数值 |
| 多页报告 | 只提取了第一页 | 提示词要求逐页提取（PDF 需逐页传图） |

### 5.3 模型选型建议

| 模型 | 用途 | 成本 |
|------|------|------|
| Claude Haiku 3.5 | 日常提取（速度快、便宜） | 低 |
| Claude Sonnet 4 | 复杂/低质量图片提取 | 中 |
| Claude Opus 4 | 调试、人工复核疑难样本 | 高 |

初始阶段用 **Haiku** 足够。如果发现提取质量不够（比如模糊图片、复杂表格），降级到 Sonnet。

---

## 6. 安全性设计

### 6.1 暂存文件安全

- `data/uploads/` 目录默认 `.gitignore`
- 文件以 session_id 命名，不保留原始文件名
- 30 分钟自动清理
- VLM 确认成功后立即清理

### 6.2 数据出域

Phase 1 使用合成数据，不存在真实 PHI 问题。但代码层面需要预留：

1. 不把原始文件名传入 VLM API（避免文件名含患者信息）
2. 在 `ocr-upload` 阶段就做基本脱敏预览
3. `deidentify_text()` 在入库前执行

### 6.3 API Key 管理

复用现有 `MODEL_API_KEY` / `MODEL_API_URL` / `MODEL_NAME` 环境变量体系。

---

## 7. 迁移路径：模式 1 → 模式 3

当未来遇到**真实患者数据 + 合规要求模型本地部署**时，需要从"VLM 端到端"切换到"PaddleOCR + 本地模型"的混合模式。

### 7.1 迁移触发条件

1. 合规审批要求数据不得离开医院内网
2. 有真实患者数据处理需求
3. 不能使用云端 API

### 7.2 迁移后的架构

```
图片/PDF → PaddleOCR(版面+文字检测) → OCR 文本+坐标 → 本地 LLM(理解) → JSON → 脱敏 → 入库
```

### 7.3 需要新增的模块

| 模块 | 用途 |
|------|------|
| `packages/clinical_intake/ocr_engine.py` | 封装 PaddleOCR / Tesseract 调用 |
| `packages/clinical_intake/layout_parser.py` | 版面分析（表格区域识别） |
| 本地模型网关 | 替代云端 API 的本地 LLM 调用 |

### 7.4 需要修改的接口

`process_image_file()` 的内部实现会变化，但对外接口保持不变（**策略模式**）：

```python
def process_image_file(...):
    engine = _get_ocr_engine()  # "vlm" | "paddle+llm"
    payload = engine.extract(image_bytes, mime_type)
    ...
```

目前只需要实现 VLM 引擎，后续加 Paddle+LLM 引擎时无需改动调用方。

### 7.5 迁移评估

> 当前无需实现。估计迁移时的工作量：**1-2 周**（PaddleOCR 安装适配 + 布局解析 + 本地模型调用）。文中描述仅供方案评估和预算参考。

---

## 8. 验证方式

### 8.1 开发期验证

```powershell
# 编译检查
python -m compileall apps packages

# 单元测试
python -m unittest tests.test_ocr -v

# 现有回归
python -m unittest tests.test_clinical_prototype
```

### 8.2 手动测试

```powershell
# 启动服务
python -m apps.api.main

# 上传测试图片
curl -X POST http://127.0.0.1:8000/api/intake/ocr-upload ^
  -F "file=@test_lab_report.png"

# 确认提取（session_id 从上传结果获取）
curl -X POST http://127.0.0.1:8000/api/intake/ocr-confirm ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"...\", \"patient_id\":\"test_001\"}"
```

### 8.3 测试数据

需要在 `test_data/` 下准备：
1. 合成化验单图片（正常范围、异常值混合）
2. 不同格式的参考范围（`3.5-5.5`、`3.5~5.5`）
3. 带影像检查的报告
4. 低质量图片（模糊、倾斜、光照不均）

---

## 9. 相关文档

| 文档 | 位置 | 用途 |
|------|------|------|
| 本项目架构概览 | `overview.md` | 项目整体定位和边界 |
| 执行计划 | `plan/ocr-plan.md` | 给执行 AI（自己）的实现参考 |
| 当前工作 | `current-work.md` | 当前进度和已知坑 |
| 项目计划 | `plan/plan.md` | 全链路计划层方案 |
| README | `README.md` | 快速上手和模块概览 |
