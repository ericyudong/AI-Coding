"""
OCR测试平台 - FastAPI主应用
"""
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from PIL import Image
import os
import uuid
import shutil
import io
import json
from datetime import datetime

from config import config_manager
from ocr_engine import OCREngineManager, OCRResult


def pdf_to_images(pdf_path: str, dpi: int = 200) -> List[Image.Image]:
    """
    将PDF文件转换为图片列表
    使用PyMuPDF (fitz) 进行转换，无需外部依赖
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise RuntimeError("PyMuPDF未安装，请运行: pip install PyMuPDF")
    
    images = []
    doc = fitz.open(pdf_path)
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        # 使用矩阵进行缩放，dpi/72 是缩放比例
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        # 转换为PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    
    doc.close()
    return images


def is_pdf_file(filename: str) -> bool:
    """检查文件是否为PDF"""
    return os.path.splitext(filename)[1].lower() == ".pdf"

# 创建FastAPI应用
app = FastAPI(
    title="OCR测试平台",
    description="支持多种OCR引擎的文档识别测试平台",
    version="1.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建上传目录
UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 初始化OCR引擎管理器
engine_manager = OCREngineManager(config_manager.get_config())

# 存储识别历史
ocr_history: List[Dict[str, Any]] = []

# 历史记录持久化文件
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "ocr_history.json")


def load_history_from_file():
    """从JSON文件加载历史记录"""
    global ocr_history
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                ocr_history = json.load(f)
        except (json.JSONDecodeError, IOError):
            ocr_history = []


def save_history_to_file():
    """将历史记录保存到JSON文件"""
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(ocr_history, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"保存历史记录失败: {e}")


# 启动时加载历史记录
load_history_from_file()


@app.get("/")
async def root():
    """返回前端页面"""
    return FileResponse("../frontend/index.html")


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "engines": engine_manager.get_engine_status()
    }


@app.get("/api/engines")
async def get_engines():
    """获取所有OCR引擎及其状态"""
    status = engine_manager.get_engine_status()
    current = config_manager.get_config().get("current_engine", "tesseract")
    
    engines = []
    for name, available in status.items():
        engines.append({
            "name": name,
            "available": available,
            "is_current": name == current
        })
    
    return {
        "engines": engines,
        "current_engine": current
    }


@app.get("/api/config")
async def get_config():
    """获取当前配置"""
    return config_manager.get_config()


@app.post("/api/config")
async def update_config(config: Dict[str, Any]):
    """更新配置"""
    try:
        # 更新配置管理器
        config_manager.update_config(config)
        
        # 更新引擎管理器
        engine_manager.update_config(config_manager.get_config())
        
        return {
            "success": True,
            "message": "配置已更新",
            "config": config_manager.get_config()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")


@app.post("/api/config/engine")
async def set_current_engine(engine_name: str = Form(...)):
    """设置当前使用的OCR引擎"""
    status = engine_manager.get_engine_status()
    
    if engine_name not in status:
        raise HTTPException(status_code=400, detail=f"未知的OCR引擎: {engine_name}")
    
    if not status[engine_name]:
        raise HTTPException(status_code=400, detail=f"OCR引擎 {engine_name} 不可用")
    
    config_manager.set_current_engine(engine_name)
    
    return {
        "success": True,
        "message": f"已切换到 {engine_name} 引擎",
        "current_engine": engine_name
    }


@app.post("/api/ocr/upload")
async def upload_and_ocr(
    file: UploadFile = File(...),
    engine: Optional[str] = Form(None)
):
    """上传文件并进行OCR识别，支持图片和PDF文件"""
    # 验证文件类型
    allowed_extensions = [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif", ".pdf"]
    filename = file.filename or "unknown.png"
    file_ext = os.path.splitext(filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {file_ext}。支持的类型: {', '.join(allowed_extensions)}"
        )
    
    # 验证文件大小 (50MB)
    max_size = 50 * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail="文件大小超过限制 (50MB)")
    
    # 保存文件
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}{file_ext}")
    
    try:
        with open(file_path, "wb") as f:
            f.write(content)
        
        # 判断是否为PDF文件
        if is_pdf_file(filename):
            # PDF文件处理：转换为图片后逐页识别
            images = pdf_to_images(file_path)
            
            if not images:
                raise HTTPException(status_code=400, detail="PDF文件无法转换为图片，可能是加密或损坏的文件")
            
            # 对每一页进行OCR识别
            page_results = []
            all_texts = []
            total_time = 0
            total_confidence = 0
            engine_name = ""
            
            for page_num, image in enumerate(images, 1):
                result = engine_manager.recognize(image, engine)
                engine_name = result.engine_name
                total_time += result.processing_time
                total_confidence += result.confidence
                
                page_text = f"--- 第 {page_num} 页 ---\n{result.text}"
                all_texts.append(page_text)
                
                page_results.append({
                    "page": page_num,
                    "text": result.text,
                    "confidence": result.confidence,
                    "processing_time": result.processing_time
                })
            
            # 合并结果
            full_text = "\n\n".join(all_texts)
            avg_confidence = total_confidence / len(images) if images else 0
            
            # 记录历史（含完整文本）
            history_item = {
                "id": file_id,
                "filename": filename,
                "engine": engine_name,
                "confidence": avg_confidence,
                "processing_time": total_time,
                "timestamp": datetime.now().isoformat(),
                "text_preview": full_text[:200] + "..." if len(full_text) > 200 else full_text,
                "full_text": full_text,
                "is_pdf": True,
                "pages": len(images)
            }
            ocr_history.insert(0, history_item)
            
            if len(ocr_history) > 100:
                ocr_history.pop()
            
            save_history_to_file()
            
            return {
                "success": True,
                "file_id": file_id,
                "filename": filename,
                "is_pdf": True,
                "total_pages": len(images),
                "result": {
                    "text": full_text,
                    "confidence": avg_confidence,
                    "processing_time": total_time,
                    "engine": engine_name,
                    "details": page_results
                }
            }
        else:
            # 图片文件处理
            image = Image.open(file_path)
            
            # 进行OCR识别
            result = engine_manager.recognize(image, engine)
            
            # 记录历史（含完整文本）
            history_item = {
                "id": file_id,
                "filename": filename,
                "engine": result.engine_name,
                "confidence": result.confidence,
                "processing_time": result.processing_time,
                "timestamp": datetime.now().isoformat(),
                "text_preview": result.text[:200] + "..." if len(result.text) > 200 else result.text,
                "full_text": result.text,
                "is_pdf": False,
                "pages": 1
            }
            ocr_history.insert(0, history_item)
            
            # 限制历史记录数量
            if len(ocr_history) > 100:
                ocr_history.pop()
            
            save_history_to_file()
            
            return {
                "success": True,
                "file_id": file_id,
                "filename": filename,
                "is_pdf": False,
                "result": {
                    "text": result.text,
                    "confidence": result.confidence,
                    "processing_time": result.processing_time,
                    "engine": result.engine_name,
                    "details": result.details
                }
            }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR识别失败: {str(e)}")
    finally:
        # 清理临时文件（可选）
        if os.path.exists(file_path):
            os.remove(file_path)


@app.post("/api/ocr/batch")
async def batch_ocr(
    files: List[UploadFile] = File(...),
    engine: Optional[str] = Form(None)
):
    """批量上传文件并进行OCR识别，支持图片和PDF"""
    results = []
    
    for file in files:
        filename = file.filename or "unknown.png"
        try:
            # 验证文件类型
            allowed_extensions = [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif", ".pdf"]
            file_ext = os.path.splitext(filename)[1].lower()
            
            if file_ext not in allowed_extensions:
                results.append({
                    "filename": filename,
                    "success": False,
                    "error": f"不支持的文件类型: {file_ext}"
                })
                continue
            
            # 读取文件
            content = await file.read()
            
            # 保存文件
            file_id = str(uuid.uuid4())
            file_path = os.path.join(UPLOAD_DIR, f"{file_id}{file_ext}")
            
            with open(file_path, "wb") as f:
                f.write(content)
            
            # 判断是否为PDF文件
            if is_pdf_file(filename):
                # PDF文件处理
                images = pdf_to_images(file_path)
                
                if not images:
                    results.append({
                        "filename": filename,
                        "success": False,
                        "error": "PDF文件无法转换为图片"
                    })
                    os.remove(file_path)
                    continue
                
                page_results = []
                all_texts = []
                total_time = 0
                total_confidence = 0
                engine_name = ""
                
                for page_num, image in enumerate(images, 1):
                    result = engine_manager.recognize(image, engine)
                    engine_name = result.engine_name
                    total_time += result.processing_time
                    total_confidence += result.confidence
                    all_texts.append(f"--- 第 {page_num} 页 ---\n{result.text}")
                    page_results.append({
                        "page": page_num,
                        "text": result.text,
                        "confidence": result.confidence
                    })
                
                full_text = "\n\n".join(all_texts)
                avg_confidence = total_confidence / len(images) if images else 0
                
                results.append({
                    "filename": filename,
                    "success": True,
                    "is_pdf": True,
                    "total_pages": len(images),
                    "result": {
                        "text": full_text,
                        "confidence": avg_confidence,
                        "processing_time": total_time,
                        "engine": engine_name,
                        "pages": page_results
                    }
                })
            else:
                # 图片文件处理
                image = Image.open(file_path)
                result = engine_manager.recognize(image, engine)
                
                results.append({
                    "filename": filename,
                    "success": True,
                    "is_pdf": False,
                    "result": {
                        "text": result.text,
                        "confidence": result.confidence,
                        "processing_time": result.processing_time,
                        "engine": result.engine_name
                    }
                })
            
            # 清理临时文件
            os.remove(file_path)
            
        except Exception as e:
            results.append({
                "filename": filename,
                "success": False,
                "error": str(e)
            })
    
    return {
        "success": True,
        "total": len(files),
        "results": results
    }


@app.get("/api/history")
async def get_history(limit: int = 20):
    """获取识别历史"""
    return {
        "history": ocr_history[:limit],
        "total": len(ocr_history)
    }


@app.get("/api/history/{item_id}")
async def get_history_item(item_id: str):
    """获取单条历史记录的完整文本"""
    for item in ocr_history:
        if item.get("id") == item_id:
            return {
                "success": True,
                "item": item
            }
    raise HTTPException(status_code=404, detail="历史记录不存在")


@app.delete("/api/history")
async def clear_history():
    """清空识别历史"""
    ocr_history.clear()
    save_history_to_file()
    return {"success": True, "message": "历史已清空"}


class ExportWordRequest(BaseModel):
    """导出Word请求体"""
    text: str
    filename: str = "OCR识别结果"
    engine: str = ""
    confidence: float = 0
    processing_time: float = 0
    is_pdf: bool = False
    total_pages: int = 0


@app.post("/api/ocr/export-word")
async def export_word(req: ExportWordRequest):
    """将OCR识别结果导出为Word文档"""
    try:
        from docx import Document
        from docx.shared import Pt, Inches, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        raise HTTPException(status_code=500, detail="python-docx未安装，请运行: pip install python-docx")
    
    from docx.oxml.ns import qn
    
    doc = Document()
    
    # 设置默认字体（必须同时设置西文和东亚字体，否则中文不显示）
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Times New Roman'
    font.size = Pt(11)
    style.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    
    # 标题
    title = doc.add_heading('OCR 识别结果', level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # 元信息
    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta_run = meta.add_run(
        f"源文件: {req.filename}"
        + (f"  |  引擎: {req.engine}" if req.engine else "")
        + (f"  |  置信度: {req.confidence * 100:.1f}%" if req.confidence else "")
        + (f"  |  耗时: {req.processing_time:.2f}s" if req.processing_time else "")
        + (f"  |  PDF共{req.total_pages}页" if req.is_pdf and req.total_pages else "")
    )
    meta_run.font.size = Pt(9)
    meta_run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    
    # 分隔线
    doc.add_paragraph('─' * 50)
    
    # 识别文本内容（按行添加，保留格式）
    from docx.enum.text import WD_BREAK
    lines = req.text.split('\n')
    first_page = True
    for line in lines:
        if line.startswith('--- 第') and '页 ---' in line:
            # PDF页码标题 - 非首页时添加分页符
            if not first_page:
                page_break_p = doc.add_paragraph()
                page_break_run = page_break_p.add_run()
                page_break_run.add_break(WD_BREAK.PAGE)
            first_page = False
            p = doc.add_paragraph()
            run = p.add_run(line)
            run.bold = True
            run.font.size = Pt(13)
            run.font.color.rgb = RGBColor(0x4f, 0x46, 0xe5)
        elif line.strip() == '':
            # 空行保留
            doc.add_paragraph('')
        else:
            para = doc.add_paragraph()
            run = para.add_run(line)
            run.font.size = Pt(11)
    
    # 页脚信息
    doc.add_paragraph('')
    footer = doc.add_paragraph()
    footer_run = footer.add_run(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  OCR测试平台")
    footer_run.font.size = Pt(8)
    footer_run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
    
    # 保存到内存
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    # 生成安全文件名
    safe_name = "".join(c for c in req.filename if c.isalnum() or c in (' ', '-', '_', '.')).strip()
    if not safe_name:
        safe_name = "OCR识别结果"
    docx_filename = f"{safe_name}_OCR结果.docx"
    
    # 使用 RFC 5987 编码中文文件名
    from urllib.parse import quote
    encoded_filename = quote(docx_filename)
    
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )


@app.get("/api/engines/status")
async def get_engines_status():
    """获取引擎详细状态"""
    status = engine_manager.get_engine_status()
    config = config_manager.get_config()
    
    return {
        "engines": {
            "tesseract": {
                "available": status.get("tesseract", False),
                "config": config.get("tesseract", {})
            },
            "paddleocr": {
                "available": status.get("paddleocr", False),
                "config": config.get("paddleocr", {})
            },
            "easyocr": {
                "available": status.get("easyocr", False),
                "config": config.get("easyocr", {})
            },
            "ovisocr": {
                "available": status.get("ovisocr", False),
                "config": config.get("ovisocr", {})
            }
        },
        "current_engine": config.get("current_engine", "tesseract")
    }


# 挂载静态文件
app.mount("/static", StaticFiles(directory="../frontend"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)