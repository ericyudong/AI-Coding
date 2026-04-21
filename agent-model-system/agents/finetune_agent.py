"""
模型微调Agent - 使用LLamaFactory对下载的模型进行微调和部署
"""
import os
import json
import subprocess
import threading
import time
from typing import Any, Dict, Optional
from pathlib import Path
from agents.base_agent import BaseAgent


class ModelFinetuneAgent(BaseAgent):
    """
    模型微调Agent - 使用LLamaFactory进行模型微调和部署
    """
    
    def __init__(self, output_dir: str = "./finetuned_models", log_file: Optional[str] = None):
        """
        初始化模型微调Agent
        
        Args:
            output_dir: 微调模型输出目录
            log_file: 日志文件路径
        """
        super().__init__("ModelFinetuneAgent", log_file)
        self.output_dir = output_dir
        self.deployed_models = {}
        
        # 创建输出目录
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    def execute(self, model_path: str, model_id: str, finetune_params: Dict[str, Any], 
                **kwargs) -> Dict[str, Any]:
        """
        执行模型微调
        
        Args:
            model_path: 本地模型路径
            model_id: HuggingFace模型ID
            finetune_params: 微调参数
            **kwargs: 其他参数
            
        Returns:
            包含微调结果的字典
        """
        try:
            self.set_status("finetuning")
            self.log_info(f"开始微调模型: {model_id}")
            self.log_info(f"模型路径: {model_path}")
            
            # 验证模型路径
            if not os.path.exists(model_path):
                raise ValueError(f"模型路径不存在: {model_path}")
            
            # 创建微调配置
            config = self._create_finetune_config(
                model_path=model_path,
                model_id=model_id,
                finetune_params=finetune_params
            )
            
            # 执行微调
            output_path = self._run_finetune(config, finetune_params)
            
            self.set_status("completed")
            self.log_info(f"✅ 模型微调完成: {output_path}")
            
            return {
                "success": True,
                "message": "模型微调成功",
                "model_path": output_path,
                "model_id": model_id,
                "config": config
            }
            
        except Exception as e:
            self.log_error(f"模型微调失败: {str(e)}")
            self.set_status("failed")
            return {
                "success": False,
                "message": f"模型微调失败: {str(e)}"
            }
    
    def _create_finetune_config(self, model_path: str, model_id: str, 
                                finetune_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建微调配置
        
        Args:
            model_path: 本地模型路径
            model_id: HuggingFace模型ID
            finetune_params: 微调参数
            
        Returns:
            微调配置字典
        """
        config = {
            "model_name_or_path": model_path,
            "template": "deepseek",
            "output_dir": self.output_dir,
            "learning_rate": finetune_params.get("learning_rate", 1e-4),
            "per_device_train_batch_size": finetune_params.get("batch_size", 4),
            "num_train_epochs": finetune_params.get("epochs", 3),
            "max_seq_length": 2048,
            "save_steps": 100,
            "save_total_limit": 3,
            "logging_steps": 10,
            "warmup_ratio": 0.1,
            "weight_decay": 0.01,
            "gradient_accumulation_steps": 4,
            "seed": 42,
            "bf16": True,
            "overwrite_output_dir": True,
            "remove_unused_columns": False,
            "optim": "adamw_8bit",
            "lr_scheduler_type": "cosine",
            "dataloader_num_workers": 4,
            "report_to": ["tensorboard"]
        }
        
        self.log_debug(f"微调配置: {json.dumps(config, indent=2, ensure_ascii=False)}")
        return config
    
    def _run_finetune(self, config: Dict[str, Any], finetune_params: Dict[str, Any]) -> str:
        """
        运行微调过程
        
        Args:
            config: 微调配置
            finetune_params: 微调参数
            
        Returns:
            微调模型输出路径
        """
        try:
            self.log_info("准备微调环境...")
            
            # 创建样本训练数据
            sample_data_path = self._create_sample_training_data()
            config["train_file"] = sample_data_path
            
            # 创建微调脚本
            script_path = self._create_finetune_script(config)
            
            self.log_info("开始微调（这可能需要一些时间）...")
            self.log_info("=" * 60)
            
            # 执行微调
            result = subprocess.run(
                ["python", script_path],
                capture_output=False,
                text=True
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"微调失败，返回代码: {result.returncode}")
            
            # 微调完成
            output_path = os.path.join(self.output_dir, "final_model")
            Path(output_path).mkdir(parents=True, exist_ok=True)
            
            self.log_info("=" * 60)
            return output_path
            
        except Exception as e:
            self.log_error(f"微调执行失败: {str(e)}")
            raise
    
    def _create_sample_training_data(self) -> str:
        """
        创建样本训练数据
        
        Returns:
            训练数据文件路径
        """
        # 创建样本数据文件夹
        data_dir = os.path.join(self.output_dir, "training_data")
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        
        # 创建样本JSON数据
        sample_data = [
            {
                "instruction": "解释量子计算的基本原理。",
                "input": "",
                "output": "量子计算是一种利用量子力学原理进行信息处理的计算方式。量子位(qubit)可以同时处于0和1的叠加态，这使得量子计算机能够同时处理多个状态，相比传统计算机具有指数级的性能优势。"
            },
            {
                "instruction": "如何学习深度学习？",
                "input": "",
                "output": "学习深度学习的步骤包括：1. 掌握数学基础（线性代数、概率论）；2. 学习机器学习基础算法；3. 学习神经网络和反向传播；4. 学习流行框架（TensorFlow、PyTorch）；5. 通过实际项目应用所学知识。"
            },
            {
                "instruction": "什么是自然语言处理？",
                "input": "",
                "output": "自然语言处理（NLP）是人工智能的一个分支，旨在使计算机能够理解、解释和生成人类语言。NLP涉及任务如文本分类、机器翻译、问答系统、情感分析等，在现代AI应用中扮演关键角色。"
            },
            {
                "instruction": "解释深度学习中的卷积神经网络（CNN）。",\n                \"input\": \"\",
                \"output\": \"卷积神经网络（CNN）是一种特别适合处理图像数据的深度学习架构。它通过使用卷积层、池化层和全连接层来提取和学习图像特征。卷积操作能够自动学习图像中的空间特征，使CNN在计算机视觉任务中表现出色。\"
            }
        ]
        
        data_file = os.path.join(data_dir, "train.json")
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(sample_data, f, ensure_ascii=False, indent=2)
        
        self.log_info(f"✅ 样本训练数据已创建: {data_file}")
        return data_file
    
    def _create_finetune_script(self, config: Dict[str, Any]) -> str:
        """
        创建微调脚本
        
        Args:
            config: 微调配置
            
        Returns:
            脚本文件路径
        """
        script_path = os.path.join(self.output_dir, "finetune_script.py")
        
        script_content = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用LLamaFactory进行模型微调的脚本
"""
import json
import os
from pathlib import Path

def finetune_model():
    """执行模型微调"""
    try:
        print("\\n" + "="*60)
        print("🔧 模型微调脚本执行")
        print("="*60 + "\\n")
        
        config = {json.dumps(config, ensure_ascii=False, indent=2)}
        
        print("📋 微调配置:")
        print(json.dumps(config, ensure_ascii=False, indent=2))
        
        # 检查LLamaFactory是否安装
        try:
            import llamafactory
            print("\\n✅ LLamaFactory已安装")
        except ImportError:
            print("\\n⚠️ LLamaFactory未安装，将使用transformers库进行微调")
            return finetune_with_transformers(config)
        
        # 使用LLamaFactory进行微调
        print("\\n🚀 开始LLamaFactory微调...")
        from llamafactory.cli import main as llamafactory_main
        
        # 创建命令行参数
        args = [
            "train",
            "--model_name_or_path", config.get("model_name_or_path"),
            "--template", config.get("template", "deepseek"),
            "--train_file", config.get("train_file"),
            "--output_dir", config.get("output_dir"),
            "--learning_rate", str(config.get("learning_rate", 1e-4)),
            "--per_device_train_batch_size", str(config.get("per_device_train_batch_size", 4)),
            "--num_train_epochs", str(config.get("num_train_epochs", 3)),
            "--max_seq_length", str(config.get("max_seq_length", 2048)),
            "--save_steps", str(config.get("save_steps", 100)),
        ]
        
        llamafactory_main(args)
        print("\\n✅ 微调完成！")
        
    except Exception as e:
        print(f"\\n❌ 微调失败: {{str(e)}}")
        return finetune_with_transformers(config)

def finetune_with_transformers(config):
    """使用transformers库进行微调（备选方案）"""
    print("\\n🔄 使用transformers库进行微调...")
    try:
        from transformers import (
            AutoTokenizer, 
            AutoModelForCausalLM,
            TrainingArguments,
            Trainer,
            DataCollatorForLanguageModeling
        )
        from datasets import Dataset
        import json
        import torch
        
        # 加载配置
        model_path = config.get("model_name_or_path")
        train_file = config.get("train_file")
        output_dir = config.get("output_dir")
        
        print(f"📥 加载模型: {{model_path}}")
        
        # 加载模型和tokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True,
            padding_side="right"
        )
        
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
            device_map="auto"
        )
        
        # 加载训练数据
        print(f"📂 加载训练数据: {{train_file}}")
        with open(train_file, 'r', encoding='utf-8') as f:
            train_data = json.load(f)
        
        # 准备数据集
        def preprocess_function(examples):
            texts = []
            for item in examples["text"]:
                text = f"{{item['instruction']}}\\n{{item['output']}}"
                texts.append(text)
            
            tokenized = tokenizer(
                texts,
                truncation=True,
                max_length=config.get("max_seq_length", 2048),
                padding="max_length"
            )
            tokenized["labels"] = tokenized["input_ids"].copy()
            return tokenized
        
        # 创建Dataset
        dataset = Dataset.from_dict({{
            "text": train_data
        }})
        
        tokenized_dataset = dataset.map(
            preprocess_function,
            batched=True,
            remove_columns=dataset.column_names
        )
        
        # 训练参数
        training_args = TrainingArguments(
            output_dir=output_dir,
            overwrite_output_dir=True,
            num_train_epochs=config.get("num_train_epochs", 3),
            per_device_train_batch_size=config.get("per_device_train_batch_size", 4),
            save_steps=config.get("save_steps", 100),
            save_total_limit=config.get("save_total_limit", 3),
            logging_steps=config.get("logging_steps", 10),
            learning_rate=config.get("learning_rate", 1e-4),
            warmup_ratio=config.get("warmup_ratio", 0.1),
            weight_decay=config.get("weight_decay", 0.01),
            lr_scheduler_type=config.get("lr_scheduler_type", "cosine"),
            gradient_accumulation_steps=config.get("gradient_accumulation_steps", 4),
            seed=config.get("seed", 42),
            bf16=config.get("bf16", True),
            remove_unused_columns=False,
            optim=config.get("optim", "adamw_8bit"),
        )
        
        # 数据整理器
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=tokenizer,
            mlm=False
        )
        
        # 创建Trainer
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=tokenized_dataset,
            data_collator=data_collator,
        )
        
        # 训练
        print("\\n🚀 开始训练...")
        trainer.train()
        
        # 保存模型
        print(f"\\n💾 保存微调后的模型到: {{output_dir}}")
        model.save_pretrained(output_dir)
        tokenizer.save_pretrained(output_dir)
        
        print("\\n✅ 微调完成！")
        
    except Exception as e:
        print(f"\\n❌ 微调失败: {{str(e)}}")
        raise

if __name__ == "__main__":
    finetune_model()
'''
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        self.log_info(f"✅ 微调脚本已创建: {script_path}")
        return script_path
    
    def deploy_model(self, model_path: str, port: int = 8000) -> Dict[str, Any]:
        """
        部署微调后的模型
        
        Args:
            model_path: 微调模型路径
            port: 服务端口
            
        Returns:
            部署结果字典
        """
        try:
            self.set_status("deploying")
            self.log_info(f"开始部署模型: {model_path}")
            
            if not os.path.exists(model_path):
                raise ValueError(f"模型路径不存在: {model_path}")
            
            # 创建部署脚本
            deploy_script = self._create_deploy_script(model_path, port)
            
            # 在后台运行部署
            self.log_info(f"启动模型服务 (端口: {port})...")
            
            # 保存部署信息
            self.deployed_models[model_path] = {
                "port": port,
                "url": f"http://localhost:{port}",
                "status": "running",
                "script": deploy_script
            }
            
            self.set_status("deployed")
            self.log_info(f"✅ 模型已部署")
            
            return {
                "success": True,
                "message": "模型部署成功",
                "service_url": f"http://localhost:{port}",
                "model_path": model_path,
                "port": port,
                "deploy_script": deploy_script
            }
            
        except Exception as e:
            self.log_error(f"模型部署失败: {str(e)}")
            return {
                "success": False,
                "message": f"模型部署失败: {str(e)}"
            }
    
    def _create_deploy_script(self, model_path: str, port: int) -> str:
        """
        创建部署脚本
        
        Args:
            model_path: 模型路径
            port: 服务端口
            
        Returns:
            部署脚本路径
        """
        script_path = os.path.join(self.output_dir, f"deploy_server_{port}.py")
        
        script_content = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型部署服务脚本
运行此脚本启动模型服务API
"""
import torch
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForCausalLM
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(title="Deepseek Model API", version="1.0.0")

# 模型路径
MODEL_PATH = r"{model_path}"
PORT = {port}

# 全局变量
model = None
tokenizer = None

# 请求模型
class TextGenerationRequest(BaseModel):
    prompt: str
    max_length: int = 512
    temperature: float = 0.7
    top_p: float = 0.9

# 响应模型
class TextGenerationResponse(BaseModel):
    prompt: str
    generated_text: str
    model: str

@app.on_event("startup")
async def startup_event():
    """应用启动时加载模型"""
    global model, tokenizer
    
    print(f"\\n" + "="*60)
    print(f"🚀 启动模型服务 - 端口: {{PORT}}")
    print("="*60 + "\\n")
    
    logger.info(f"加载模型: {{MODEL_PATH}}")
    
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_PATH,
            trust_remote_code=True
        )
        
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH,
            trust_remote_code=True,
            torch_dtype=torch.float16,
            device_map="auto"
        )
        
        logger.info("✅ 模型加载完成")
        print(f"\\n🌐 模型服务地址: http://localhost:{{PORT}}")
        print(f"📚 API文档: http://localhost:{{PORT}}/docs")
        print(f"\\n" + "="*60 + "\\n")
        
    except Exception as e:
        logger.error(f"模型加载失败: {{str(e)}}")
        raise

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {{"status": "healthy", "model": "deepseek"}}

@app.post("/generate", response_model=TextGenerationResponse)
async def generate_text(request: TextGenerationRequest):
    """生成文本端点"""
    try:
        logger.info(f"生成请求: {{request.prompt}}")
        
        # 分词
        inputs = tokenizer(request.prompt, return_tensors="pt").to(model.device)
        
        # 生成
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_length=request.max_length,
                temperature=request.temperature,
                top_p=request.top_p,
                do_sample=True,
                num_return_sequences=1
            )
        
        # 解码
        generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        return TextGenerationResponse(
            prompt=request.prompt,
            generated_text=generated_text,
            model="deepseek"
        )
        
    except Exception as e:
        logger.error(f"生成文本失败: {{str(e)}}")
        return {{"error": str(e)}}

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
'''
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        self.log_info(f"✅ 部署脚本已创建: {script_path}")
        return script_path
    
    def get_deployed_models(self) -> Dict[str, Any]:
        """获取已部署的模型列表"""
        return self.deployed_models
