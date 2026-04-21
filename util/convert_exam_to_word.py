#!/usr/bin/env python3
"""
Convert algorithm exam questions to Word format
"""

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
import re

def create_document():
    """Create a new Word document"""
    doc = Document()
    
    # Set document default font
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Microsoft YaHei'
    font.size = Pt(12)
    
    return doc

def add_main_title(doc, text):
    """Add main title"""
    heading = doc.add_heading(text, level=0)
    for run in heading.runs:
        run.font.name = 'Microsoft YaHei'
        run.font.bold = True
        run.font.size = Pt(22)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return heading

def add_section_title(doc, text, level=1):
    """Add section title"""
    if level == 1:
        heading = doc.add_heading(text, level=1)
        for run in heading.runs:
            run.font.name = 'Microsoft YaHei'
            run.font.bold = True
            run.font.size = Pt(18)
    else:
        heading = doc.add_heading(text, level=2)
        for run in heading.runs:
            run.font.name = 'Microsoft YaHei'
            run.font.bold = True
            run.font.size = Pt(15)
    return heading

def add_paragraph(doc, text, bold=False, font_size=None):
    """Add a paragraph"""
    p = doc.add_paragraph()
    if text.strip():
        run = p.add_run(text)
        run.font.name = 'Microsoft YaHei'
        run.font.bold = bold
        if font_size:
            run.font.size = Pt(font_size)
    return p

def add_list_item(doc, text, level=0):
    """Add a list item"""
    indent = '    ' * level
    p = doc.add_paragraph(indent + text, style='List Bullet')
    for run in p.runs:
        run.font.name = 'Microsoft YaHei'
    return p

def add_numbered_item(doc, number, text):
    """Add a numbered item"""
    p = doc.add_paragraph(f"{number}. {text}", style='List Number')
    for run in p.runs:
        run.font.name = 'Microsoft YaHei'
    return p

def create_exam_document():
    """Create the exam document"""
    doc = create_document()
    
    # Title
    add_main_title(doc, "机器学习、深度学习与大模型算法笔试题")
    add_paragraph(doc, "总分：100分")
    doc.add_paragraph()
    
    # Section 1: 选择题
    add_section_title(doc, "一、选择题（每题2分，共20分）")
    
    questions = [
        ("1. 在梯度下降算法中，学习率（learning rate）过大可能导致（ ）",
         "A. 收敛速度变慢  B. 永远无法收敛  C. 陷入局部最优  D. 参数更新幅度过小"),
        ("2. 下列哪种激活函数会导致梯度消失问题（ ）",
         "A. ReLU  B. Sigmoid  C. Leaky ReLU  D. GELU"),
        ("3. Transformer模型中使用的位置编码（Positional Encoding）主要目的是（ ）",
         "A. 加快训练速度  B. 引入序列位置信息  C. 减少模型参数  D. 提高泛化能力"),
        ("4. BERT模型采用的双向编码器架构主要是为了（ ）",
         "A. 减少计算量  B. 捕获上下文信息  C. 加速推理  D. 降低内存占用"),
        ("5. L1正则化与L2正则化的主要区别是（ ）",
         "A. L1可以产生稀疏解  B. L2收敛更快  C. L1不可导  D. L2效果更好"),
        ("6. 下面哪个不是注意力机制（Attention）的组成部分（ ）",
         "A. Query  B. Key  C. Value  D. Bias"),
        ("7. 在Word2Vec中，Skip-gram模型的输入是（ ）",
         "A. 中心词，输出是上下文词  B. 上下文词，输出是中心词  C. 词向量，输出是词向量  D. 语法树，输出是词向量"),
        ("8. 预训练大语言模型时，next token prediction属于（ ）",
         "A. 判别任务  B. 生成任务  C. 判别和生成都是  D. 既不是判别也不是生成"),
        ("9. 以下哪种技术不能减少过拟合（ ）",
         "A. Dropout  B. 数据增强  C. 增加模型参数  D. 早停法"),
        ("10. GPT和BERT的主要区别是（ ）",
         "A. GPT是自编码，BERT是自回归  B. GPT是单向，BERT是双向  C. GPT用于理解任务，BERT用于生成任务  D. GPT参数更少"),
    ]
    
    for q, options in questions:
        add_paragraph(doc, q)
        add_paragraph(doc, options)
        doc.add_paragraph()
    
    # Section 2: 简答题
    add_section_title(doc, "二、简答题（每题8分，共40分）")
    
    saqs = [
        "1. 请简述梯度下降法的三种变体：批量梯度下降、随机梯度下降、小批量梯度下降的优缺点。（8分）",
        "2. 解释什么是梯度消失和梯度爆炸问题，以及解决这两种问题的常用方法。（8分）",
        "3. 详细说明Transformer中Self-Attention的工作原理，包括Q、K、V的计算和Attention Score的计算过程。（8分）",
        "4. 什么是过拟合？请列出至少4种防止过拟合的方法，并简要说明原理。（8分）",
        "5. 请解释大语言模型中的涌现能力（Emergent Abilities）是什么，并举例说明。（8分）",
    ]
    
    for sq in saqs:
        add_paragraph(doc, sq)
    
    # Section 3: 计算题
    add_section_title(doc, "三、计算题（共20分）")
    
    add_paragraph(doc, "1. 逻辑回归损失函数（12分）")
    add_paragraph(doc, "已知逻辑回归的交叉熵损失函数为：L(y, ŷ) = -[y log(ŷ) + (1-y) log(1-ŷ)]")
    add_paragraph(doc, "其中 ŷ = σ(w^T x + b)，σ(z) = 1/(1+e^(-z))")
    add_paragraph(doc, "请推导：当使用单个样本 (x_i, y_i) 计算梯度时，∂L/∂w_j 的表达式是什么？")
    doc.add_paragraph()
    
    add_paragraph(doc, "2. Softmax梯度计算（8分）")
    add_paragraph(doc, "假设有一个3分类问题，softmax输出为 ŷ = [0.2, 0.5, 0.3]，真实标签为 y = [0, 1, 0]（one-hot编码）。")
    add_paragraph(doc, "请计算：交叉熵损失值，以及对第二个输出节点 z_2 的梯度 ∂L/∂z_2。")
    
    # Section 4: 算法设计题
    add_section_title(doc, "四、算法设计题（共20分）")
    
    add_paragraph(doc, "1. 请设计一个用于文本相似度计算的算法，给定两个句子，输出它们的相似度分数。（10分）")
    add_paragraph(doc, "要求：考虑词序和语义信息、时间复杂度尽量低、可以使用现有的预训练模型")
    doc.add_paragraph()
    
    add_paragraph(doc, "2. 给定一个长度为n的输入序列，设计一个算法找出其中的最长递增子序列（LIS）。（10分）")
    add_paragraph(doc, "要求：写出时间复杂度和空间复杂度、如果使用动态规划，请写出状态转移方程、可以考虑使用二分优化")
    
    # Section 5: 参考答案
    add_section_title(doc, "参考答案")
    
    # 选择题答案
    add_paragraph(doc, "一、选择题答案", bold=True)
    add_paragraph(doc, "1. B  2. B  3. B  4. B  5. A")
    add_paragraph(doc, "6. D  7. A  8. B  9. C  10. B")
    
    # 简答题要点
    add_paragraph(doc, "", bold=True)
    add_paragraph(doc, "二、简答题要点", bold=True)
    
    add_paragraph(doc, "1. 梯度下降三种变体")
    add_paragraph(doc, "批量梯度下降(BGD)：每次使用全部样本计算梯度")
    add_paragraph(doc, "  - 优点：收敛稳定，方向准确")
    add_paragraph(doc, "  - 缺点：计算量大，内存要求高")
    add_paragraph(doc, "随机梯度下降(SGD)：每次使用单个样本计算梯度")
    add_paragraph(doc, "  - 优点：计算快，可跳出局部最优")
    add_paragraph(doc, "  - 缺点：收敛震荡，方向不稳定")
    add_paragraph(doc, "小批量梯度下降(Mini-batch GD)：每次使用batch_size个样本")
    add_paragraph(doc, "  - 优点：兼顾效率和稳定性")
    add_paragraph(doc, "  - 缺点：batch_size需要调参")
    
    add_paragraph(doc, "", bold=True)
    add_paragraph(doc, "2. 梯度消失/爆炸及解决方法")
    add_paragraph(doc, "梯度消失：深层网络或激活函数饱和导致梯度接近0")
    add_paragraph(doc, "  - 解决方法：ReLU激活、残差连接、Batch Normalization、梯度裁剪")
    add_paragraph(doc, "梯度爆炸：连乘导致梯度指数级增长")
    add_paragraph(doc, "  - 解决方法：梯度裁剪、使用L2正则、选择合适学习率")
    
    add_paragraph(doc, "", bold=True)
    add_paragraph(doc, "3. Transformer Self-Attention原理")
    add_paragraph(doc, "1) 输入embedding分别通过三个线性层得到Q、K、V")
    add_paragraph(doc, "2) 计算Attention Score：A = QK^T / sqrt(d_k)")
    add_paragraph(doc, "3) Softmax归一化：S = softmax(A)")
    add_paragraph(doc, "4) 输出：O = SV")
    
    add_paragraph(doc, "", bold=True)
    add_paragraph(doc, "4. 防止过拟合方法")
    add_paragraph(doc, "- Dropout：随机失活神经元")
    add_paragraph(doc, "- 数据增强：增加训练样本多样性")
    add_paragraph(doc, "- 早停法：验证集性能下降时停止训练")
    add_paragraph(doc, "- 正则化：L1/L2惩罚复杂模型")
    add_paragraph(doc, "- 集成学习：多个模型投票")
    
    add_paragraph(doc, "", bold=True)
    add_paragraph(doc, "5. 大模型涌现能力")
    add_paragraph(doc, "指模型在规模达到一定量级后，突然出现在小模型中不存在的能力，如：")
    add_paragraph(doc, "- 思维链(Chain-of-Thought)推理")
    add_paragraph(doc, "- 零样本学习能力")
    add_paragraph(doc, "- 跨任务迁移能力")
    
    # 计算题答案
    add_paragraph(doc, "", bold=True)
    add_paragraph(doc, "三、计算题答案", bold=True)
    add_paragraph(doc, "1. 逻辑回归梯度推导")
    add_paragraph(doc, "∂L/∂w_j = (ŷ - y) · x_j")
    add_paragraph(doc, "", bold=True)
    add_paragraph(doc, "2. Softmax梯度计算")
    add_paragraph(doc, "损失值：L = -log(0.5) ≈ 0.693")
    add_paragraph(doc, "梯度：∂L/∂z_2 = 0.5 - 1 = -0.5")
    
    # Footer
    doc.add_paragraph()
    add_paragraph(doc, "出题人：AI算法组")
    add_paragraph(doc, "考试时间：120分钟")
    
    return doc

def main():
    output_file = r'c:\eswin\emaas\ML_DL_LLM_算法笔试题.docx'
    
    print("Creating exam document...")
    doc = create_exam_document()
    
    print(f"Saving to: {output_file}")
    doc.save(output_file)
    
    print(f"Successfully created: {output_file}")

if __name__ == '__main__':
    main()