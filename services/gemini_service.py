import io
import os

from google import genai
from google.genai import types


TRANSCRIPTION_PROMPT = (
    "You are a note transcription assistant. "
    "The images contain handwritten notes. "
    "Please transcribe all the content into a single, well-structured Markdown document. "
    "Preserve the original structure and hierarchy as much as possible. "
    "Use appropriate Markdown elements such as headings, bullet points, numbered lists, bold/italic text, and code blocks where relevant. "
    "Do not add any commentary — output only the Markdown content."
)

def get_gemini_client():
    return genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

async def transcribe_images_to_markdown(image_inputs: list[dict]) -> str:
    client = get_gemini_client()
    
    contents = []

    for image in image_inputs:
        contents.append(
            types.Part(
                inline_data=types.Blob(
                    mime_type=image["content_type"],
                    data=image["content"]
                )
            )
        )

    
    contents.append(TRANSCRIPTION_PROMPT)

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=8192,
            )
        )
    except Exception as e:
        print(f"Primary model 'gemini-3-flash-preview' failed: {e}. Falling back to 'gemini-3.1-flash-lite-preview'.")
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=8192,
            )
        )

    return response.text.strip()