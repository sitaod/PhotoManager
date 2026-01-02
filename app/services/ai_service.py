"""
AI Service Module for Qwen Vision-Language Model Integration

This module provides AI-powered image analysis and tag generation
using Alibaba Cloud's Tongyi Qianwen (Qwen) vision model.
"""

import base64
import json
import os
from typing import List, Optional

from openai import OpenAI


def encode_image_to_base64(image_path: str) -> str:
    """
    Encode a local image file to Base64 string.
    
    Args:
        image_path: Absolute path to the image file
        
    Returns:
        Base64 encoded string of the image
        
    Raises:
        FileNotFoundError: If image file does not exist
        IOError: If file cannot be read
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    try:
        with open(image_path, 'rb') as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        raise IOError(f"Failed to read image file: {str(e)}")


def generate_tags_from_image(image_path: str, api_key: str, base_url: str, model: str) -> List[str]:
    """
    Generate descriptive tags for an image using Qwen vision model.
    
    This function sends the image to Qwen's vision-language model and requests
    it to analyze the content and generate 3-5 concise Chinese tags.
    
    Args:
        image_path: Absolute path to the image file
        api_key: Qwen API key from DashScope
        base_url: API base URL (dashscope.aliyuncs.com/compatible-mode/v1)
        model: Model name (e.g., 'qwen-vl-max')
        
    Returns:
        List of Chinese tag strings (3-5 tags)
        Returns empty list if API call fails
        
    Example:
        >>> tags = generate_tags_from_image('/path/to/sunset.jpg', api_key, base_url, model)
        >>> print(tags)
        ['风景', '日落', '大海', '自然']
    """
    try:
        # Step 1: Encode image to Base64
        base64_image = encode_image_to_base64(image_path)
        
        # Step 2: Construct image URL in data URI format
        image_url = f"data:image/jpeg;base64,{base64_image}"
        
        # Step 3: Design prompt for tag generation
        prompt = """请仔细分析这张图片的内容，并生成3-5个简洁、准确的中文标签。

要求：
1. 标签应该描述图片的主要内容、场景、物体或主题
2. 每个标签限制在2-4个汉字
3. 按重要性排序，最重要的标签放在前面
4. 以JSON格式返回，格式为: {"tags": ["标签1", "标签2", "标签3"]}

请只返回JSON，不要包含其他解释文字。"""
        
        # Step 4: Initialize OpenAI client with Qwen credentials
        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        # Step 5: Make API request
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            temperature=0.3,  # Lower temperature for more consistent results
            max_tokens=200    # Limit response length
        )
        
        # Step 6: Extract and parse response
        response_content = completion.choices[0].message.content
        
        # Try to parse JSON from response
        # Sometimes the model may include markdown code blocks, so we need to clean it
        response_content = response_content.strip()
        if response_content.startswith('```json'):
            response_content = response_content[7:]  # Remove ```json
        if response_content.startswith('```'):
            response_content = response_content[3:]  # Remove ```
        if response_content.endswith('```'):
            response_content = response_content[:-3]  # Remove trailing ```
        response_content = response_content.strip()
        
        # Parse JSON
        try:
            result = json.loads(response_content)
            tags = result.get('tags', [])
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract tags manually
            # Look for patterns like ["tag1", "tag2"]
            import re
            tags_match = re.search(r'\[(.*?)\]', response_content)
            if tags_match:
                tags_str = tags_match.group(1)
                tags = [tag.strip(' "\'') for tag in tags_str.split(',')]
            else:
                print(f"Failed to parse tags from response: {response_content}")
                return []
        
        # Step 7: Validate and clean tags
        if not isinstance(tags, list):
            print(f"Invalid tags format: {tags}")
            return []
        
        # Filter out empty tags and limit to 5 tags
        cleaned_tags = [tag.strip() for tag in tags if isinstance(tag, str) and tag.strip()]
        cleaned_tags = cleaned_tags[:5]  # Limit to maximum 5 tags
        
        print(f"Successfully generated {len(cleaned_tags)} AI tags: {cleaned_tags}")
        return cleaned_tags
        
    except FileNotFoundError as e:
        print(f"Image file error: {str(e)}")
        return []
    except IOError as e:
        print(f"File I/O error: {str(e)}")
        return []
    except Exception as e:
        print(f"Error generating AI tags: {str(e)}")
        # In case of any error, return empty list to avoid breaking the upload flow
        return []


def generate_tags_safely(image_path: str, api_key: str, base_url: str, model: str) -> Optional[List[str]]:
    """
    Safely generate tags with additional error handling wrapper.
    
    This is a convenience function that wraps generate_tags_from_image
    with additional safety measures.
    
    Args:
        image_path: Absolute path to the image file
        api_key: Qwen API key
        base_url: API base URL
        model: Model name
        
    Returns:
        List of tags if successful, None if failed
    """
    if not api_key:
        print("Warning: Qwen API key not configured. Skipping AI tag generation.")
        return None
    
    if not os.path.exists(image_path):
        print(f"Warning: Image file does not exist: {image_path}")
        return None
    
    tags = generate_tags_from_image(image_path, api_key, base_url, model)
    return tags if tags else None
