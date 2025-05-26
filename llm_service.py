import os
import json
import tempfile
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import re
import docx
import PyPDF2
from io import BytesIO


@dataclass
class LLMConfig:
    provider: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


@dataclass
class ProcessedSegment:
    type: str
    title: str
    content: str
    tags: List[str]


@dataclass
class ProcessedCourse:
    courseTitle: str
    overview: str
    tags: List[str]
    segments: List[ProcessedSegment]


class DocumentProcessor:
    """文檔處理器 - 支持多種文件格式"""
    
    @staticmethod
    def extract_text_from_file(file_path: str, filename: str) -> str:
        """從文件中提取文本內容"""
        try:
            file_extension = filename.lower().split('.')[-1]
            
            if file_extension == 'txt':
                return DocumentProcessor._extract_text_from_txt(file_path)
            elif file_extension == 'md':
                return DocumentProcessor._extract_text_from_md(file_path)
            elif file_extension == 'docx':
                return DocumentProcessor._extract_text_from_docx(file_path)
            elif file_extension == 'pdf':
                return DocumentProcessor._extract_text_from_pdf(file_path)
            else:
                raise ValueError(f"不支援的文件格式: {file_extension}")
                
        except Exception as e:
            raise Exception(f"文件處理失敗 {filename}: {str(e)}")
    
    @staticmethod
    def _extract_text_from_txt(file_path: str) -> str:
        """提取 TXT 文件內容"""
        encodings = ['utf-8', 'gbk', 'big5', 'cp936']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    return file.read()
            except UnicodeDecodeError:
                continue
        
        raise Exception("無法讀取文本文件，請檢查文件編碼")
    
    @staticmethod
    def _extract_text_from_md(file_path: str) -> str:
        """提取 Markdown 文件內容"""
        return DocumentProcessor._extract_text_from_txt(file_path)
    
    @staticmethod
    def _extract_text_from_docx(file_path: str) -> str:
        """提取 DOCX 文件內容"""
        try:
            doc = docx.Document(file_path)
            text_content = []
            
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_content.append(paragraph.text.strip())
            
            return '\n\n'.join(text_content)
            
        except Exception as e:
            raise Exception(f"DOCX 文件處理失敗: {str(e)}")
    
    @staticmethod
    def _extract_text_from_pdf(file_path: str) -> str:
        """提取 PDF 文件內容"""
        try:
            text_content = []
            
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text.strip():
                            text_content.append(page_text.strip())
                    except Exception as e:
                        print(f"PDF 第 {page_num + 1} 頁處理失敗: {str(e)}")
                        continue
            
            if not text_content:
                raise Exception("PDF 文件中沒有找到可提取的文本")
            
            return '\n\n'.join(text_content)
            
        except Exception as e:
            raise Exception(f"PDF 文件處理失敗: {str(e)}")


class LLMProcessor:
    """LLM 處理器 - 支持多種 AI 服務"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        
        # 根據提供者設置請求處理器
        if config.provider == 'openai':
            self.processor = self._process_with_openai
        elif config.provider == 'gemini':
            self.processor = self._process_with_gemini
        elif config.provider == 'ollama':
            self.processor = self._process_with_ollama
        else:
            raise ValueError(f"不支援的 LLM 提供者: {config.provider}")
    
    def process_documents(self, documents_text: str, course_info: Dict[str, Any]) -> ProcessedCourse:
        """處理文檔並生成結構化課程內容"""
        
        # 構建提示詞
        prompt = self._build_prompt(documents_text, course_info)
        
        # 調用 LLM
        response = self.processor(prompt)
        
        # 解析響應
        return self._parse_llm_response(response, course_info)
    
    def _build_prompt(self, documents_text: str, course_info: Dict[str, Any]) -> str:
        """構建給 LLM 的提示詞"""
        
        course_title = course_info.get('courseTitle', '')
        course_domain = course_info.get('courseDomain', '')
        additional_tags = course_info.get('additionalTags', '')
        
        prompt = f"""
請幫我把這個課程講義、課堂資料，整理成以下內容:

課程標題: {course_title}
課程領域: {course_domain}
附加標籤: {additional_tags}

1. 第一部分
包含課程標題
課程概述 - 課堂主要內容、處理的問題等...
課程標籤 - 主要領域標籤

2. 第二部分
將內容分成數個段落，一個段落描述一件事，每個段落包含:
- 段落類型 - 從「內容、診斷、治療、理論、案例、其它」中選擇
- 段落標題
- 段落內容
- 標籤 - 從「手法、症狀、位置、施術位置、治療位置、領域、病因、其它」這幾個分類中選擇，輸出格式為"分類:內容"，例如"手法:揉法"、"症狀:疼痛"、"位置:肩部"、"施術位置:肘關節"等

請以 JSON 格式輸出，結構如下:
{{
  "courseTitle": "課程標題",
  "overview": "課程概述內容",
  "tags": ["標籤1", "標籤2", "標籤3"],
  "segments": [
    {{
      "type": "段落類型",
      "title": "段落標題",
      "content": "段落詳細內容",
      "tags": ["手法:推拿", "症狀:疼痛", "位置:頸部"]
    }}
  ]
}}

課程資料內容:
{documents_text}

請仔細分析內容，生成結構化的課程資料。確保:
1. 段落內容要完整詳細
2. 標籤要準確反映內容重點
3. 段落類型要恰當分類
4. JSON 格式要正確
"""
        
        return prompt
    
    def _process_with_openai(self, prompt: str) -> str:
        """使用 OpenAI API 處理"""
        headers = {
            'Authorization': f'Bearer {self.config.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.config.model or 'gpt-3.5-turbo',
            'messages': [
                {
                    'role': 'system',
                    'content': '你是一個專業的課程整理助手，擅長將非結構化的教學資料整理成結構化的課程內容。'
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': 0.3,
            'max_tokens': 4000
        }
        
        response = requests.post(
            f"{self.config.base_url}/chat/completions",
            headers=headers,
            json=data,
            timeout=120
        )
        
        if response.status_code != 200:
            raise Exception(f"OpenAI API 錯誤: {response.status_code} - {response.text}")
        
        result = response.json()
        return result['choices'][0]['message']['content']
    
    def _process_with_gemini(self, prompt: str) -> str:
        """使用 Google Gemini API 處理"""
        headers = {
            'Content-Type': 'application/json'
        }
        
        data = {
            'contents': [
                {
                    'parts': [
                        {
                            'text': prompt
                        }
                    ]
                }
            ],
            'generationConfig': {
                'temperature': 0.3,
                'maxOutputTokens': 4000,
                'topP': 0.95,
                'topK': 40
            }
        }
        
        model = self.config.model or 'gemini-pro'
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.config.api_key}"
        
        response = requests.post(url, headers=headers, json=data, timeout=120)
        
        if response.status_code != 200:
            raise Exception(f"Gemini API 錯誤: {response.status_code} - {response.text}")
        
        result = response.json()
        
        if 'candidates' not in result or not result['candidates']:
            raise Exception("Gemini API 沒有返回有效響應")
        
        return result['candidates'][0]['content']['parts'][0]['text']
    
    def _process_with_ollama(self, prompt: str) -> str:
        """使用 Ollama 本地服務處理"""
        headers = {
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.config.model or 'llama2',
            'prompt': prompt,
            'stream': False,
            'options': {
                'temperature': 0.3,
                'num_predict': 4000
            }
        }
        
        response = requests.post(
            f"{self.config.base_url}/api/generate",
            headers=headers,
            json=data,
            timeout=300  # Ollama 可能需要更長時間
        )
        
        if response.status_code != 200:
            raise Exception(f"Ollama API 錯誤: {response.status_code} - {response.text}")
        
        result = response.json()
        return result.get('response', '')
    
    def _parse_llm_response(self, response: str, course_info: Dict[str, Any]) -> ProcessedCourse:
        """解析 LLM 響應並返回結構化數據"""
        try:
            # 提取 JSON 內容
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            
            if not json_match:
                # 如果沒有找到 JSON，嘗試其他方法解析
                return self._fallback_parse(response, course_info)
            
            json_str = json_match.group(0)
            data = json.loads(json_str)
            
            # 驗證和清理數據
            course_title = data.get('courseTitle') or course_info.get('courseTitle', '未命名課程')
            overview = data.get('overview') or '課程概述暫無'
            tags = data.get('tags') or []
            
            segments = []
            for seg_data in data.get('segments', []):
                segment = ProcessedSegment(
                    type=seg_data.get('type', '內容'),
                    title=seg_data.get('title', '未命名段落'),
                    content=seg_data.get('content', ''),
                    tags=seg_data.get('tags', [])
                )
                segments.append(segment)
            
            # 如果沒有段落，創建一個默認段落
            if not segments:
                segments.append(ProcessedSegment(
                    type='內容',
                    title='課程內容',
                    content=response[:500] + '...' if len(response) > 500 else response,
                    tags=[course_info.get('courseDomain', '其它')]
                ))
            
            return ProcessedCourse(
                courseTitle=course_title,
                overview=overview,
                tags=tags,
                segments=segments
            )
            
        except json.JSONDecodeError as e:
            print(f"JSON 解析失敗: {e}")
            return self._fallback_parse(response, course_info)
        
        except Exception as e:
            print(f"響應解析失敗: {e}")
            return self._fallback_parse(response, course_info)
    
    def _fallback_parse(self, response: str, course_info: Dict[str, Any]) -> ProcessedCourse:
        """備用解析方法 - 當 JSON 解析失敗時使用"""
        print("使用備用解析方法")
        
        # 基本信息
        course_title = course_info.get('courseTitle', '課程')
        overview = "AI 處理生成的課程概述"
        tags = [course_info.get('courseDomain', '其它')]
        
        # 將響應分段
        paragraphs = [p.strip() for p in response.split('\n\n') if p.strip()]
        
        segments = []
        for i, paragraph in enumerate(paragraphs[:10]):  # 限制段落數量
            if len(paragraph) > 50:  # 過濾太短的段落
                segment = ProcessedSegment(
                    type='內容',
                    title=f'段落 {i + 1}',
                    content=paragraph,
                    tags=[course_info.get('courseDomain', '其它')]
                )
                segments.append(segment)
        
        # 確保至少有一個段落
        if not segments:
            segments.append(ProcessedSegment(
                type='內容',
                title='課程內容',
                content=response[:1000] if response else '內容處理中出現問題',
                tags=['其它']
            ))
        
        return ProcessedCourse(
            courseTitle=course_title,
            overview=overview,
            tags=tags,
            segments=segments
        )


class LLMCourseService:
    """LLM 課程服務 - 主要服務類"""
    
    @staticmethod
    def test_ollama_connection(base_url: str) -> Dict[str, Any]:
        """測試 Ollama 連接並獲取可用模型"""
        try:
            # 測試連接
            response = requests.get(f"{base_url}/api/tags", timeout=10)
            
            if response.status_code == 200:
                models_data = response.json()
                models = [model['name'] for model in models_data.get('models', [])]
                
                return {
                    'success': True,
                    'models': models
                }
            else:
                return {
                    'success': False,
                    'error': f"連接失敗，狀態碼: {response.status_code}"
                }
                
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f"連接錯誤: {str(e)}"
            }
    
    @staticmethod
    def process_course_files(files, form_data) -> ProcessedCourse:
        """處理課程文件的主要方法"""
        
        # 1. 提取文檔內容
        documents_text = ""
        temp_files = []
        
        try:
            for file in files:
                # 保存臨時文件
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{file.filename.split('.')[-1]}")
                file.save(temp_file.name)
                temp_files.append(temp_file.name)
                
                # 提取文本
                try:
                    text = DocumentProcessor.extract_text_from_file(temp_file.name, file.filename)
                    documents_text += f"\n\n=== {file.filename} ===\n{text}\n"
                except Exception as e:
                    print(f"文件 {file.filename} 處理失敗: {e}")
                    continue
            
            if not documents_text.strip():
                raise Exception("沒有成功提取到任何文檔內容")
            
            # 2. 配置 LLM
            config = LLMConfig(
                provider=form_data.get('apiProvider'),
                api_key=form_data.get('apiKey'),
                base_url=form_data.get('baseUrl'),
                model=form_data.get('model')
            )
            
            # 3. 處理課程信息
            course_info = {
                'courseTitle': form_data.get('courseTitle'),
                'courseDomain': form_data.get('courseDomain'),
                'additionalTags': form_data.get('additionalTags')
            }
            
            # 4. 調用 LLM 處理
            processor = LLMProcessor(config)
            result = processor.process_documents(documents_text, course_info)
            
            return result
            
        finally:
            # 清理臨時文件
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass
    
    @staticmethod
    def save_processed_course(processed_data: Dict[str, Any], course_info: Dict[str, Any]) -> int:
        """將處理後的課程數據保存到數據庫"""
        from datetime import datetime
        from models import db, Session, Segment, Tag
        from app import CATEGORY_COLORS
        
        try:
            # 創建課程
            session = Session(
                title=processed_data.get('courseTitle', course_info.get('courseTitle', '未命名課程')),
                overview=processed_data.get('overview', ''),
                date=datetime.fromisoformat(course_info.get('courseDate')) if course_info.get('courseDate') else datetime.now()
            )
            
            # 處理課程標籤
            course_tags = processed_data.get('tags', [])
            if course_info.get('courseDomain'):
                course_tags.append(course_info['courseDomain'])
            
            if course_info.get('additionalTags'):
                additional_tags = [tag.strip() for tag in course_info['additionalTags'].split(',') if tag.strip()]
                course_tags.extend(additional_tags)
            
            for tag_name in set(course_tags):  # 去重
                if tag_name.strip():
                    tag = Tag.query.filter_by(name=tag_name.strip()).first()
                    if not tag:
                        tag = Tag(
                            name=tag_name.strip(),
                            category='領域',
                            color=CATEGORY_COLORS.get('領域', '#6c757d')
                        )
                        db.session.add(tag)
                        db.session.flush()
                    session.tags.append(tag)
            
            db.session.add(session)
            db.session.flush()  # 獲取 session.id
            
            # 處理段落
            for order_index, segment_data in enumerate(processed_data.get('segments', [])):
                segment = Segment(
                    session_id=session.id,
                    segment_type=segment_data.get('type', '內容'),
                    title=segment_data.get('title', f'段落 {order_index + 1}'),
                    content=segment_data.get('content', ''),
                    order_index=order_index + 1
                )
                
                # 處理段落標籤
                segment_tags = segment_data.get('tags', [])
                for tag_info in segment_tags:
                    if ':' in tag_info:
                        # 格式化標籤: "分類:內容"
                        category, tag_name = tag_info.split(':', 1)
                        category = category.strip()
                        tag_name = tag_name.strip()
                    else:
                        # 普通標籤
                        tag_name = tag_info.strip()
                        category = '其它'
                    
                    if tag_name:
                        tag = Tag.query.filter_by(name=tag_name).first()
                        if not tag:
                            tag = Tag(
                                name=tag_name,
                                category=category,
                                color=CATEGORY_COLORS.get(category, '#6c757d')
                            )
                            db.session.add(tag)
                            db.session.flush()
                        segment.tags.append(tag)
                
                db.session.add(segment)
            
            db.session.commit()
            return session.id
            
        except Exception as e:
            db.session.rollback()
            raise Exception(f"保存課程失敗: {str(e)}")
