#!/usr/bin/env python3
"""
Convert algorithm exam answers to Word format
"""

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

def create_document():
    doc = Document()
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Microsoft YaHei'
    font.size = Pt(12)
    return doc

def add_main_title(doc, text):
    heading = doc.add_heading(text, level=0)
    for run in heading.runs:
        run.font.name = 'Microsoft YaHei'
        run.font.bold = True
        run.font.size = Pt(22)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

def add_section_title(doc, text):
    heading = doc.add_heading(text, level=1)
    for run in heading.runs:
        run.font.name = 'Microsoft YaHei'
        run.font.bold = True
        run.font.size = Pt(18)

def add_subsection_title(doc, text):
    heading = doc.add_heading(text, level=2)
    for run in heading.runs:
        run.font.name = 'Microsoft YaHei'
        run.font.bold = True
        run.font.size = Pt(15)

def add_p(doc, text, bold=False, indent=0):
    p = doc.add_paragraph()
    if indent > 0:
        p.paragraph_format.left_indent = Pt(indent * 20)
    if text:
        run = p.add_run(text)
        run.font.name = 'Microsoft YaHei'
        run.font.bold = bold

def add_formula(doc, formula):
    p = doc.add_paragraph()
    run = p.add_run(formula)
    run.font.name = 'Consolas'
    run.font.size = Pt(11)

def create_answer_document():
    doc = create_document()
    
    add_main_title(doc, "机器学习、深度学习与大模型算法笔试题参考答案")
    add_p(doc, "总分：100分")
    doc.add_paragraph()
    
    # 选择题
    add_section_title(doc, "一、选择题答案（每题2分，共20分）")
    
    answers = [
        ("1", "B", "学习率过大会导致参数更新幅度过大，无法收敛到最优解，甚至可能发散。"),
        ("2", "B", "Sigmoid函数的导数在两端接近0，在深层网络中会导致梯度逐层衰减，造成梯度消失。"),
        ("3", "B", "Transformer使用位置编码是为了让模型能够区分序列中不同位置的token，捕获序列的顺序信息。"),
        ("4", "B", "BERT的双向编码器可以同时利用左右两侧的上下文信息，更好地理解语义。"),
        ("5", "A", "L1正则化会产生稀疏解（使部分参数为0），L2正则化会使参数趋近于0但不会为0。"),
        ("6", "D", "注意力机制由Query、Key、Value三部分组成，Bias不是其组成部分。"),
        ("7", "A", "Skip-gram模型以中心词作为输入，预测其上下文词。"),
        ("8", "B", "Next token prediction是典型的生成任务，让模型根据已有序列预测下一个token。"),
        ("9", "C", "增加模型参数会加重过拟合问题，而不是减少过拟合。"),
        ("10", "B", "GPT是单向自回归模型，BERT是双向编码器模型。"),
    ]
    
    for num, answer, reason in answers:
        add_p(doc, f"{num}. 答案：{answer}", bold=True)
        add_p(doc, f"   解析：{reason}", indent=1)
        doc.add_paragraph()
    
    # 简答题
    add_section_title(doc, "二、简答题答案（共40分）")
    
    add_subsection_title(doc, "1. 梯度下降法的三种变体（8分）")
    add_p(doc, "（1）批量梯度下降（Batch Gradient Descent, BGD）", bold=True)
    add_p(doc, "• 每次使用全部训练样本计算梯度", indent=1)
    add_p(doc, "• 优点：收敛方向准确，迭代稳定", indent=1)
    add_p(doc, "• 缺点：计算量大，内存要求高，难以处理大规模数据集", indent=1)
    
    add_p(doc, "（2）随机梯度下降（Stochastic Gradient Descent, SGD）", bold=True)
    add_p(doc, "• 每次使用单个样本计算梯度", indent=1)
    add_p(doc, "• 优点：计算速度快，可以跳出局部最优", indent=1)
    add_p(doc, "• 缺点：收敛震荡剧烈，方向不稳定", indent=1)
    
    add_p(doc, "（3）小批量梯度下降（Mini-batch Gradient Descent）", bold=True)
    add_p(doc, "• 每次使用batch_size个样本（通常32-256）", indent=1)
    add_p(doc, "• 优点：兼顾计算效率和收敛稳定性", indent=1)
    add_p(doc, "• 缺点：batch_size需要人工调参", indent=1)
    doc.add_paragraph()
    
    add_subsection_title(doc, "2. 梯度消失与梯度爆炸（8分）")
    add_p(doc, "【梯度消失】", bold=True)
    add_p(doc, "• 定义：在深层神经网络中，由于激活函数的饱和特性或链式法则，连乘导致梯度逐层指数级衰减，最终接近0。", indent=1)
    add_p(doc, "• 解决方法：", indent=1)
    add_p(doc, "  - 使用ReLU/Leaky ReLU等非饱和激活函数", indent=2)
    add_p(doc, "  - 残差连接（ResNet）让梯度直接回传", indent=2)
    add_p(doc, "  - Batch Normalization规范化激活值", indent=2)
    add_p(doc, "  - 梯度裁剪防止梯度过小", indent=2)
    
    add_p(doc, "【梯度爆炸】", bold=True)
    add_p(doc, "• 定义：网络层数过深或权重初始化过大，连乘导致梯度指数级增长，参数更新幅度过大。", indent=1)
    add_p(doc, "• 解决方法：", indent=1)
    add_p(doc, "  - 梯度裁剪（gradient clipping）", indent=2)
    add_p(doc, "  - L2正则化", indent=2)
    add_p(doc, "  - 合理的权重初始化（如Xavier、He初始化）", indent=2)
    add_p(doc, "  - 选择合适的学习率", indent=2)
    doc.add_paragraph()
    
    add_subsection_title(doc, "3. Transformer Self-Attention原理（8分）")
    add_p(doc, "Self-Attention（自注意力）机制是Transformer的核心组件，工作流程如下：", indent=1)
    
    add_p(doc, "【步骤1：生成Q、K、V】", bold=True)
    add_p(doc, "将输入embedding分别通过三个独立的线性变换层：", indent=1)
    add_formula(doc, "Q = XW_Q  (Query矩阵)")
    add_formula(doc, "K = XW_K  (Key矩阵)")
    add_formula(doc, "V = XW_V  (Value矩阵)")
    add_p(doc, "其中W_Q、W_K、W_V是可学习的权重矩阵。", indent=1)
    
    add_p(doc, "【步骤2：计算Attention Score】", bold=True)
    add_formula(doc, "Attention Score = (Q x K^T) / sqrt(d_k)")
    add_p(doc, "除以sqrt(d_k)是为了缩放，防止点积结果过大导致softmax梯度极小。", indent=1)
    
    add_p(doc, "【步骤3：Softmax归一化】", bold=True)
    add_formula(doc, "alpha = softmax(Attention Score)")
    add_p(doc, "将scores转化为概率分布，所有权重之和为1。", indent=1)
    
    add_p(doc, "【步骤4：计算输出】", bold=True)
    add_formula(doc, "Output = alpha x V = softmax(QK^T/sqrt(d_k)) x V")
    add_p(doc, "最终输出是Value的加权和，权重由Query和Key的相似度决定。", indent=1)
    
    add_p(doc, "【Multi-Head Attention】", bold=True)
    add_p(doc, "使用多头注意力：并行计算多个attention，然后将结果拼接", indent=1)
    add_formula(doc, "MultiHead(Q,K,V) = Concat(head_1, ..., head_h)W^O")
    doc.add_paragraph()
    
    add_subsection_title(doc, "4. 过拟合及防止方法（8分）")
    add_p(doc, "【过拟合定义】", bold=True)
    add_p(doc, "模型在训练集上表现良好，但在测试集/新数据上表现较差，泛化能力不足。", indent=1)
    
    add_p(doc, "【防止过拟合的方法】（至少4种）", bold=True)
    add_p(doc, "（1）Dropout：随机冻结部分神经元，减少模型对特定节点的依赖", indent=1)
    add_p(doc, "（2）数据增强：通过对训练数据进行变换（旋转、裁剪、加噪声等）增加样本多样性", indent=1)
    add_p(doc, "（3）早停法（Early Stopping）：当验证集性能下降时停止训练", indent=1)
    add_p(doc, "（4）正则化：L1/L2惩罚大的权重，降低模型复杂度", indent=1)
    add_p(doc, "（5）集成学习：使用多个模型的投票结果，降低单一模型的偏差", indent=1)
    add_p(doc, "（6）降低模型复杂度：减少网络层数或神经元数量", indent=1)
    add_p(doc, "（7）交叉验证：更可靠地评估模型泛化能力", indent=1)
    doc.add_paragraph()
    
    add_subsection_title(doc, "5. 大模型涌现能力（8分）")
    add_p(doc, "【定义】", bold=True)
    add_p(doc, "涌现能力（Emergent Abilities）是指大型语言模型在规模达到一定量级后，突然涌现出在小模型中不存在的能力。这些能力不是通过训练直接获得的，而是在模型参数规模增大后自然出现的。", indent=1)
    
    add_p(doc, "【典型例子】", bold=True)
    add_p(doc, "（1）思维链推理（Chain-of-Thought, CoT）", indent=1)
    add_p(doc, "模型可以展示逐步推理的过程，解决复杂的数学或逻辑问题。", indent=2)
    
    add_p(doc, "（2）零样本学习（Zero-shot Learning）", indent=1)
    add_p(doc, "模型可以在没有见过特定任务样本的情况下，完成新任务。", indent=2)
    
    add_p(doc, "（3）少样本学习（Few-shot Learning）", indent=1)
    add_p(doc, "只需给少量示例，模型就能理解并执行新任务。", indent=2)
    
    add_p(doc, "（4）指令跟随（Instruction Following）", indent=1)
    add_p(doc, "模型能够理解自然语言指令并执行相应操作。", indent=2)
    
    add_p(doc, "（5）多语言能力", indent=1)
    add_p(doc, "模型可以处理和翻译未在训练集中明确对应的语言对。", indent=2)
    
    add_p(doc, "【涌现的阈值】", bold=True)
    add_p(doc, "研究表明，涌现能力通常在模型规模超过某个阈值（如100B参数）后突然出现，这个现象被称为涌现。", indent=1)
    doc.add_paragraph()
    
    # 计算题
    add_section_title(doc, "三、计算题答案（共20分）")
    
    add_subsection_title(doc, "1. 逻辑回归梯度推导（12分）")
    add_p(doc, "【已知条件】", bold=True)
    add_p(doc, "损失函数：L = -[y log(yhat) + (1-y) log(1-yhat)]")
    add_p(doc, "预测值：yhat = sigma(w^T x + b) = 1/(1+e^-(w^Tx+b))")
    add_p(doc, "Sigmoid导数：sigma'(z) = sigma(z)(1-sigma(z))")
    
    add_p(doc, "【推导过程】", bold=True)
    add_formula(doc, "dL/dw_j = dL/dyhat x dyhat/dz x dz/dw_j")
    add_formula(doc, "其中 z = w^Tx + b")
    
    add_p(doc, "Step 1: dL/dyhat")
    add_formula(doc, "dL/dyhat = -[y/yhat - (1-y)/(1-yhat)]")
    
    add_p(doc, "Step 2: dyhat/dz = yhat(1-yhat)")
    
    add_p(doc, "Step 3: dz/dw_j = x_j")
    
    add_p(doc, "【综合】", bold=True)
    add_formula(doc, "dL/dw_j = -[y/yhat - (1-y)/(1-yhat)] x yhat(1-yhat) x x_j")
    add_formula(doc, "       = -[y(1-yhat) - (1-y)yhat] x x_j")
    add_formula(doc, "       = -(y - yhat) x x_j")
    add_formula(doc, "       = (yhat - y) x x_j")
    
    add_p(doc, "【最终答案】", bold=True)
    add_formula(doc, "dL/dw_j = (yhat - y) · x_j")
    add_p(doc, "这表明梯度等于预测误差乘以输入特征值。", indent=1)
    doc.add_paragraph()
    
    add_subsection_title(doc, "2. Softmax梯度计算（8分）")
    add_p(doc, "【已知条件】", bold=True)
    add_p(doc, "softmax输出：yhat = [0.2, 0.5, 0.3]")
    add_p(doc, "真实标签（one-hot）：y = [0, 1, 0]")
    add_p(doc, "交叉熵损失：L = -Σ y_i log(yhat_i)")
    
    add_p(doc, "【计算损失值】", bold=True)
    add_formula(doc, "L = -[0xlog(0.2) + 1xlog(0.5) + 0xlog(0.3)]")
    add_formula(doc, "L = -log(0.5)")
    add_formula(doc, "L ≈ 0.693")
    
    add_p(doc, "【计算梯度 dL/dz_2】", bold=True)
    add_p(doc, "对于交叉熵 + softmax，梯度有一个简洁形式：")
    add_formula(doc, "dL/dz_i = yhat_i - y_i")
    
    add_p(doc, "因此：")
    add_formula(doc, "dL/dz_2 = yhat_2 - y_2 = 0.5 - 1 = -0.5")
    
    add_p(doc, "【验证】", bold=True)
    add_p(doc, "使用链式法则验证：", indent=1)
    add_formula(doc, "dL/dz_2 = dL/dyhat_2 x dyhat_2/dz_2")
    add_formula(doc, "       = (-1/0.5) x [0.5x(1-0.5)]")
    add_formula(doc, "       = (-2) x 0.25 = -0.5")
    
    add_p(doc, "【最终答案】", bold=True)
    add_p(doc, "损失值：L ≈ 0.693")
    add_p(doc, "梯度：dL/dz_2 = -0.5")
    doc.add_paragraph()
    
    # 算法设计题
    add_section_title(doc, "四、算法设计题答案（共20分）")
    
    add_subsection_title(doc, "1. 文本相似度计算算法（10分）")
    add_p(doc, "【算法设计】", bold=True)
    add_p(doc, "方案一：基于预训练模型的语义相似度（推荐）", indent=1)
    add_p(doc, "时间复杂度：O(n)，n为句子长度", indent=1)
    add_p(doc, "优点：捕获语义信息，不受词序影响；预训练模型效果好", indent=1)
    
    add_p(doc, "方案二：传统方法（TF-IDF + 余弦相似度）", indent=1)
    add_p(doc, "时间复杂度：O(n + m)，n、m为句子词汇量", indent=1)
    add_p(doc, "优点：计算简单，速度快；缺点：不捕获语义和词序", indent=1)
    doc.add_paragraph()
    
    add_subsection_title(doc, "2. 最长递增子序列算法（10分）")
    add_p(doc, "【动态规划解法】", bold=True)
    add_p(doc, "时间复杂度：O(n²)，空间复杂度：O(n)", indent=1)
    
    add_p(doc, "状态定义：", indent=1)
    add_p(doc, "dp[i] = 以第i个元素结尾的最长递增子序列长度", indent=2)
    
    add_p(doc, "状态转移方程：", bold=True)
    add_formula(doc, "dp[i] = max(dp[j] + 1)，其中 j < i 且 arr[j] < arr[i]")
    
    add_p(doc, "初始化：dp[i] = 1（每个元素本身是一个长度为1的递增子序列）", indent=1)
    
    add_p(doc, "【二分优化解法】", bold=True)
    add_p(doc, "时间复杂度：O(n log n)，空间复杂度：O(n)", indent=1)
    add_p(doc, "使用二分查找维护一个递增数组tails，tails[i]表示长度为i+1的递增子序列的最小结尾值。", indent=1)
    
    add_p(doc, "【关键点】", bold=True)
    add_p(doc, "二分法利用了tails数组的有序性", indent=1)
    add_p(doc, "对于每个元素，用O(log n)时间找到其位置", indent=1)
    add_p(doc, "证明：tails数组始终保持递增，且tails[i]是所有长度i+1递增子序列的最小结尾", indent=1)
    doc.add_paragraph()
    
    add_section_title(doc, "参考答案完")
    
    return doc

def main():
    output_file = r'c:\eswin\emaas\ML_DL_LLM_算法笔试题答案.docx'
    
    print("Creating answer document...")
    doc = create_answer_document()
    
    print(f"Saving to: {output_file}")
    doc.save(output_file)
    
    print(f"Successfully created: {output_file}")

if __name__ == '__main__':
    main()