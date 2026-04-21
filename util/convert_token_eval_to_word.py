#!/usr/bin/env python3
"""
Convert Token Efficiency Evaluation Guide to Word format
"""

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
import re
import sys
import os

def read_markdown_file(filepath):
    """Read the markdown file content"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def create_document():
    """Create a new Word document"""
    doc = Document()
    
    # Set document default font
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Microsoft YaHei'
    font.size = Pt(12)
    
    return doc

def add_title(doc, text, level=1):
    """Add a title to the document"""
    if level == 1:
        heading = doc.add_heading(text, level=0)
    elif level == 2:
        heading = doc.add_heading(text, level=1)
    else:
        heading = doc.add_heading(text, level=2)
    
    # Set title font
    for run in heading.runs:
        run.font.name = 'Microsoft YaHei'
        run.font.bold = True
        if level == 1:
            run.font.size = Pt(22)
        elif level == 2:
            run.font.size = Pt(18)
        else:
            run.font.size = Pt(15)
    
    return heading

def add_paragraph(doc, text, bold=False, italic=False, font_size=None):
    """Add a paragraph to the document"""
    p = doc.add_paragraph()
    
    if text.strip():
        run = p.add_run(text)
        run.font.name = 'Microsoft YaHei'
        run.font.bold = bold
        run.font.italic = italic
        if font_size:
            run.font.size = Pt(font_size)
    
    return p

def add_code_block(doc, text):
    """Add a code block to the document"""
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.name = 'Consolas'
    run.font.size = Pt(10)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    
    return p

def add_table(doc, headers, rows):
    """Add a table to the document"""
    table = doc.add_table(rows=len(rows)+1, cols=len(headers))
    table.style = 'Light Grid Accent 1'
    
    # Add header row
    header_cells = table.rows[0].cells
    for i, header in enumerate(headers):
        header_cells[i].text = header
        for paragraph in header_cells[i].paragraphs:
            for run in paragraph.runs:
                run.font.bold = True
                run.font.name = 'Microsoft YaHei'
    
    # Add data rows
    for row_idx, row_data in enumerate(rows):
        row_cells = table.rows[row_idx+1].cells
        for col_idx, cell_data in enumerate(row_data):
            row_cells[col_idx].text = cell_data
            for paragraph in row_cells[col_idx].paragraphs:
                for run in paragraph.runs:
                    run.font.name = 'Microsoft YaHei'
    
    return table

def process_markdown(content):
    """Process markdown content and add to document"""
    doc = create_document()
    lines = content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Skip empty lines at the beginning
        if not line.strip() and i < 10:
            i += 1
            continue
        
        # Process headings
        if line.startswith('# '):
            add_title(doc, line[2:], level=1)
        elif line.startswith('## '):
            add_title(doc, line[3:], level=2)
        elif line.startswith('### '):
            add_title(doc, line[4:], level=3)
        
        # Process horizontal rules
        elif line.strip() == '---':
            doc.add_paragraph()
            p = doc.add_paragraph()
            p.add_run('_' * 50)
        
        # Process unordered lists
        elif line.strip().startswith('- '):
            text = line.strip()[2:]
            p = doc.add_paragraph(text, style='List Bullet')
            for run in p.runs:
                run.font.name = 'Microsoft YaHei'
        
        # Process numbered lists
        elif re.match(r'^\d+\.\s', line.strip()):
            match = re.match(r'^(\d+)\.\s(.*)', line.strip())
            if match:
                text = match.group(2)
                p = doc.add_paragraph(text, style='List Number')
                for run in p.runs:
                    run.font.name = 'Microsoft YaHei'
        
        # Process code blocks (fenced)
        elif line.strip().startswith('```'):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            if code_lines:
                add_code_block(doc, '\n'.join(code_lines))
        
        # Process tables (simple markdown table detection)
        elif '|' in line and i + 2 < len(lines) and '|' in lines[i+1] and '-' in lines[i+1]:
            # This is a table
            table_lines = [line]
            i += 1
            # Skip the separator line
            if i < len(lines) and '-' in lines[i]:
                i += 1
            # Read table rows
            table_rows = []
            while i < len(lines) and '|' in lines[i]:
                row_data = [cell.strip() for cell in lines[i].split('|') if cell.strip()]
                if row_data:
                    table_rows.append(row_data)
                i += 1
            
            if table_rows:
                # First row as header
                headers = table_rows[0]
                rows = table_rows[1:] if len(table_rows) > 1 else []
                add_table(doc, headers, rows)
            continue
        
        # Process emphasis (bold, italic)
        elif '**' in line:
            # Create paragraph with formatted text
            p = doc.add_paragraph()
            parts = re.split(r'(\*\*[^*]+\*\*)', line)
            for part in parts:
                if part.startswith('**') and part.endswith('**'):
                    run = p.add_run(part[2:-2])
                    run.font.bold = True
                else:
                    run = p.add_run(part)
                run.font.name = 'Microsoft YaHei'
        
        # Process regular paragraphs
        elif line.strip():
            p = doc.add_paragraph(line.strip())
            for run in p.runs:
                run.font.name = 'Microsoft YaHei'
        
        i += 1
    
    return doc

def main():
    # Input and output file paths - Token Evaluation Guide
    input_file = r'c:\eswin\emaas\大模型Token生成效率评估指南.md'
    output_file = r'c:\大模型Token生成效率评估指南.docx'
    
    print(f"Reading markdown file: {input_file}")
    content = read_markdown_file(input_file)
    
    print("Converting to Word format...")
    doc = process_markdown(content)
    
    print(f"Saving to: {output_file}")
    doc.save(output_file)
    
    print(f"Successfully created: {output_file}")

if __name__ == '__main__':
    main()