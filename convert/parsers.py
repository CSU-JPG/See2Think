import re
import json
import os
from data_schema import TaskData, Step, StepImage

class MarkdownParser:
    def __init__(self):
        # 匹配 Step 标题
        self.step_header_pattern = re.compile(
            r'(?:^|\n)'                   # 1. 开头：必须是行首或前一个是换行符
            r'(?:\*\*|##?|\s)*'           # 2. 前缀：允许 **, ##, 或空格
            r'Step\s+(\d+)'               # 3. 核心：Step + 数字 (捕获组1)
            r'(?:.*?)?'                   # 4. 中间：非贪婪匹配可能存在的 (Text) 等
            r'(?:\*\*|##?)?'              # 5. 后缀：允许 ** 或 ##
            r'(?::|\s*\n|$)',             # 6. 结束：匹配冒号、(空格+换行) 或 字符串结束
            re.IGNORECASE
        )
        
        # 匹配 Final Answer
        self.final_answer_pattern = re.compile(
            r'(?:^|\n)(?:\*\*|##?|\s)*Final Answer(?:\*\*|##?)?[:\s]*(.*)', 
            re.IGNORECASE | re.DOTALL
        )
        
        self.json_block_pattern = re.compile(r'```json\s*([\s\S]*?)\s*```', re.IGNORECASE)
        self.code_block_pattern = re.compile(r'```(\w*)\s*([\s\S]*?)\s*```')
        self.image_pattern = re.compile(r'!\[.*?\]\((.*?)\)')
        self.boxed_pattern = re.compile(r'\\boxed\{(?P<content>.*?)\}')

    def clean_text_content(self, text: str) -> str:
        """深度清洗文本：去除 markdown 残留、多余空行"""
        if not text:
            return ""
        # 1. 去除开头可能残留的 ** 或 :
        text = re.sub(r'^(?:\*\*|:|\s)+', '', text)
        # 2. 去除结尾可能残留的 **
        text = re.sub(r'(?:\*\*|\s)+$', '', text)
        # 3. 压缩多余换行
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def parse_q_md(self, file_path: str) -> dict:
        if not os.path.exists(file_path):
            return {"question": "", "answer": ""}
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        parts = re.split(r'(?:\*\*|\#)?\s*Answer:\s*', content, maxsplit=1)
        question = parts[0].strip()
        answer = parts[1].strip() if len(parts) > 1 else ""
        
        # 去除 question 和 answer 中的图片链接
        question = self.image_pattern.sub('', question).strip()
        answer = self.image_pattern.sub('', answer).strip()
        
        return {"question": question, "answer": answer}

    def parse_steps_md(self, file_path: str, base_dir: str) -> dict:
        if not os.path.exists(file_path):
            return {"steps": [], "final_answer": "", "success": False, "error": "File not found"}

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        result = {
            "steps": [],
            "final_answer": "",
            "success": True,
            "error": ""
        }

        try:
            # 1. 提取 Final Answer
            fa_match = self.final_answer_pattern.search(content)
            if fa_match:
                raw_answer = fa_match.group(1).strip()
                # 清洗 Final Answer (处理 \boxed{})
                boxed_match = self.boxed_pattern.search(raw_answer)
                if boxed_match:
                    raw_answer = boxed_match.group("content")
                result["final_answer"] = self.clean_text_content(raw_answer)
                
                content_for_steps = content[:fa_match.start()]
            else:
                content_for_steps = content

            # 2. 切分 Steps (Raw split)
            matches = list(self.step_header_pattern.finditer(content_for_steps))
            raw_steps = []
            
            for i, match in enumerate(matches):
                step_num = int(match.group(1))
                start_pos = match.end()
                end_pos = matches[i+1].start() if i + 1 < len(matches) else len(content_for_steps)
                
                step_raw_content = content_for_steps[start_pos:end_pos] # 不在这里 strip，保留格式用于后续提取
                parsed_step = self._analyze_step_content(step_num, step_raw_content, base_dir)
                raw_steps.append(parsed_step)

            # 合并相同 index 的步骤
            result["steps"] = self._merge_duplicate_steps(raw_steps)

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)

        return result

    def _analyze_step_content(self, index: int, content: str, base_dir: str) -> Step:
        step = Step(step_index=index)
        
        # A. 提取并移除 JSON
        json_matches = list(self.json_block_pattern.finditer(content))
        for jm in json_matches:
            json_str = jm.group(1)
            try:
                # 尝试解析 JSON
                data = json.loads(json_str)
                # 如果 action_json 已经存在（极少见），合并或覆盖
                if step.action_json:
                    if isinstance(step.action_json, dict) and isinstance(data, dict):
                        step.action_json.update(data)
                else:
                    step.action_json = data
            except json.JSONDecodeError:
                step.code_block = (step.code_block or "") + "\n[JSON Error]: " + json_str
            content = content.replace(jm.group(0), "")

        # B. 提取并移除 其他代码块
        code_matches = list(self.code_block_pattern.finditer(content))
        for cm in code_matches:
            lang = cm.group(1)
            if lang.lower() == 'json': continue 
            code_content = cm.group(2).strip()
            
            if step.code_block:
                # 如果一个步骤里有多个代码块，用换行符拼接
                step.code_block += "\n\n" + code_content
            else:
                step.code_block = code_content
            # 从原文中移除该代码块
            content = content.replace(cm.group(0), "")

        # C. 提取图片链接
        # 查找所有图片链接
        img_matches = self.image_pattern.findall(content)
        
        # 遍历找到的图片，验证是否存在，取第一个有效的
        for img_rel_path in img_matches:
            if 'p0.png' in img_rel_path: continue # 忽略题目图
            
            # 构建绝对路径
            abs_path = os.path.join(base_dir, img_rel_path)
            
            # 校验存在性
            if os.path.exists(abs_path):
                # 找到第一个有效的，赋值并退出循环（保证一对一）
                step.image = StepImage(
                    relative_path=img_rel_path,
                    absolute_path=abs_path
                )
                break 
            # 如果不存在，打印日志
            else:
                print(f"Warning: Image not found at {abs_path} for Step {index}")

        # 移除正文中的所有图片链接，保持文本干净
        content = self.image_pattern.sub("", content)

        # D. 清洗剩余文本
        step.content_text = self.clean_text_content(content)

        return step

    def _merge_duplicate_steps(self, raw_steps: list[Step]) -> list[Step]:
        if not raw_steps: return []
        
        merged = []
        current = raw_steps[0]
        
        for next_step in raw_steps[1:]:
            if next_step.step_index == current.step_index:
                # 合并文本
                if next_step.content_text:
                    if current.content_text:
                        current.content_text += "\n\n" + next_step.content_text
                    else:
                        current.content_text = next_step.content_text
                
                # 合并 Action
                if next_step.action_json and not current.action_json:
                    current.action_json = next_step.action_json
                
                # 合并代码块
                if next_step.code_block:
                    current.code_block = (current.code_block or "") + next_step.code_block
                
                # 合并图片：如果当前没图，但下一段有图，就拿过来
                if not current.image and next_step.image:
                    current.image = next_step.image
                    
            else:
                merged.append(current)
                current = next_step
        
        merged.append(current)
        return merged