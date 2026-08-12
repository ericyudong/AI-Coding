# OCR测试平台

一个用于测试OCR模型效果的Web平台，支持文档上传、OCR识别和模型配置。

## 功能特性

- **文档上传**: 支持拖拽或点击上传图片文档（PNG、JPG、JPEG、TIFF、BMP、GIF）和 PDF 文件
- **PDF支持**: 自动将 PDF 每页转换为图片并逐页识别，结果按页合并展示
- **多引擎支持**: 集成 Tesseract、PaddleOCR、EasyOCR、OvisOCR 四种OCR引擎
- **模型配置**: 可视化配置各OCR引擎参数（语言、PSM、OEM、GPU等）
- **引擎切换**: 支持在页面中切换默认OCR引擎
- **识别历史**: 记录识别历史，支持查看和清空
- **结果导出**: 支持复制识别文本或下载为TXT文件

## 项目结构

```
ocr-test-platform/
├── backend/                # 后端服务
│   ├── main.py            # FastAPI主应用
│   ├── config.py          # 配置管理
│   ├── ocr_engine.py      # OCR引擎模块
│   └── requirements.txt   # Python依赖
├── frontend/              # 前端页面
│   ├── index.html         # 主页面
│   ├── css/
│   │   └── style.css      # 样式文件
│   └── js/
│       └── app.js         # 前端脚本
├── run.bat                # Windows启动脚本
├── run.sh                 # Linux/Mac启动脚本
└── README.md              # 项目说明
```

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 安装OCR引擎（至少安装一个）

#### Tesseract（推荐，轻量）
- Windows: 下载安装 https://github.com/UB-Mannheim/tesseract/wiki
- 安装时勾选需要的语言包（如 chi_sim 简体中文）
- 默认安装路径: `C:\Program Files\Tesseract-OCR\tesseract.exe`

#### PaddleOCR（高精度）
```bash
pip install paddlepaddle paddleocr
```

#### EasyOCR（多语言）
```bash
pip install easyocr
```

### 3. 启动服务

**Windows:**
```bash
run.bat
```

**Linux/Mac:**
```bash
chmod +x run.sh
./run.sh
```

或手动启动:
```bash
cd backend
python main.py
```

### 4. 访问平台

- 主界面: http://localhost:8000
- API文档: http://localhost:8000/docs

## 使用说明

### 文档上传与识别

1. 进入「文档上传」页面
2. 选择OCR引擎（或使用默认引擎）
3. 拖拽或点击上传图片文件或 PDF 文件
4. 点击「开始识别」
5. 查看识别结果，可复制或下载文本

### 模型配置

1. 进入「模型配置」页面
2. 查看各引擎状态（可用/未安装）
3. 配置引擎参数：
   - **Tesseract**: 路径、语言、PSM、OEM
   - **PaddleOCR**: 语言、GPU、文字方向分类
   - **EasyOCR**: 语言列表、GPU
4. 配置通用参数（预处理、去噪、二值化）
5. 点击「保存配置」

### 切换默认引擎

在「模型配置」页面的「引擎状态」区域，点击可用引擎旁的「设为默认」按钮。

## API接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/engines` | 获取引擎列表 |
| GET | `/api/engines/status` | 获取引擎详细状态 |
| GET | `/api/config` | 获取当前配置 |
| POST | `/api/config` | 更新配置 |
| POST | `/api/config/engine` | 设置默认引擎 |
| POST | `/api/ocr/upload` | 上传并识别 |
| POST | `/api/ocr/batch` | 批量识别 |
| GET | `/api/history` | 获取识别历史 |
| DELETE | `/api/history` | 清空历史 |

## 配置说明

配置文件保存在 `backend/ocr_config.json`，首次运行会自动创建默认配置。

```json
{
  "current_engine": "tesseract",
  "tesseract": {
    "path": "C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
    "lang": "chi_sim+eng",
    "psm": 3,
    "oem": 3
  },
  "paddleocr": {
    "use_gpu": false,
    "lang": "ch",
    "use_angle_cls": true
  },
  "easyocr": {
    "lang_list": ["ch_sim", "en"],
    "gpu": false
  },
  "general": {
    "preprocess": true,
    "denoise": true,
    "threshold": true
  }
}
```

## 常见问题

### Tesseract 无法识别中文
确保安装时勾选了中文语言包，或手动下载 `chi_sim.traineddata` 放到 `tessdata` 目录。

### PaddleOCR 首次运行慢
首次运行会下载模型文件（约100MB），请耐心等待。

### 识别效果不佳
1. 尝试在配置页面开启/关闭预处理选项
2. 调整PSM模式（如单行文本用PSM 7）
3. 尝试切换其他OCR引擎

## 技术栈

- **后端**: Python + FastAPI
- **前端**: HTML5 + CSS3 + JavaScript
- **OCR引擎**: Tesseract / PaddleOCR / EasyOCR / OvisOCR
- **PDF处理**: PyMuPDF
