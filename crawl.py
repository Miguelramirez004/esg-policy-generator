import os
import json
import asyncio
import requests
from xml.etree import ElementTree
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse
from dotenv import load_dotenv
import time
import traceback
from bs4 import BeautifulSoup

# Import OpenAI for embeddings
from litellm import AsyncOpenAI

# Import database functionality
from db import init_collection

# Load environment variables
load_dotenv()

@dataclass
class ProcessedChunk:
    url: str
    chunk_number: int
    title: str
    summary: str
    content: str
    metadata: Dict[str, Any]
    embedding: List[float]

def chunk_text(text: str, chunk_size: int = 5000) -> List[str]:
    """Split text into chunks, respecting code blocks and paragraphs."""
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        if end >= text_length:
            chunks.append(text[start:].strip())
            break

        chunk = text[start:end]
        code_block = chunk.rfind("```")
        if code_block != -1 and code_block > chunk_size * 0.3:
            end = start + code_block
        elif "\n\n" in chunk:
            last_break = chunk.rfind("\n\n")
            if last_break > chunk_size * 0.3:
                end = start + last_break
        elif ". " in chunk:
            last_period = chunk.rfind(". ")
            if last_period > chunk_size * 0.3:
                end = start + last_period + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = max(start + 1, end)

    return chunks

async def get_title_and_summary(chunk: str, url: str, openai_client: AsyncOpenAI) -> Dict[str, str]:
    """Extract title and summary using an LLM."""
    system_prompt = """You are an AI that extracts titles and summaries from web content chunks.
    Return a JSON object with 'title' and 'summary' keys.
    For the title: If this seems like the start of a document, extract its title. If it's a middle chunk, derive a descriptive title.
    For the summary: Create a concise summary of the main points in this chunk.
    Keep both title and summary concise but informative.
    """

    try:
        response = await openai_client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-4-0125-preview"),
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"URL: {url}\n\nContent:\n{chunk[:1000]}...",
                },
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error getting title and summary: {e}")
        return {
            "title": "Error processing title",
            "summary": "Error processing summary",
        }

async def get_embedding(text: str, openai_client: AsyncOpenAI) -> List[float]:
    """Get embedding vector from OpenAI."""
    try:
        response = await openai_client.embeddings.create(
            model="text-embedding-3-small", input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return [0] * 1536

async def process_chunk(chunk: str, chunk_number: int, url: str, openai_client: AsyncOpenAI) -> ProcessedChunk:
    """Process a single chunk of text."""
    extracted = await get_title_and_summary(chunk, url, openai_client)
    embedding = await get_embedding(chunk, openai_client)

    metadata = {
        "source": urlparse(url).netloc,
        "chunk_size": len(chunk),
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        "url_path": urlparse(url).path,
        "url": url,
    }

    return ProcessedChunk(
        url=url,
        chunk_number=chunk_number,
        title=extracted["title"],
        summary=extracted["summary"],
        content=chunk,
        metadata=metadata,
        embedding=embedding,
    )

async def insert_chunk(chunk: ProcessedChunk, chroma_collection):
    """Insert a processed chunk into ChromaDB."""
    try:
        chroma_collection.add(
            documents=[chunk.content],
            embeddings=[chunk.embedding],
            metadatas=[
                {
                    "url": chunk.url,
                    "chunk_number": chunk.chunk_number,
                    "title": chunk.title,
                    "summary": chunk.summary,
                    **chunk.metadata,
                }
            ],
            ids=[f"{chunk.url}_{chunk.chunk_number}"],
        )
        print(f"Inserted chunk {chunk.chunk_number} for {chunk.url}")
    except Exception as e:
        print(f"Error inserting chunk: {e}")

def html_to_markdown(html_content: str) -> str:
    """Convert HTML to a simplified markdown-like format."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove scripts, styles
    for script in soup(["script", "style"]):
        script.extract()
    
    # Get text and add some markdown-like formatting
    text = soup.get_text(separator='\n')
    
    # Find headings and make them markdown
    for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        level = int(heading.name[1])
        heading_text = heading.get_text().strip()
        if heading_text:
            text = text.replace(heading_text, f"{'#' * level} {heading_text}")
    
    # Find links
    for link in soup.find_all('a'):
        link_text = link.get_text().strip()
        href = link.get('href')
        if link_text and href:
            text = text.replace(link_text, f"[{link_text}]({href})")
    
    # Clean up extra whitespace
    text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
    
    return text

async def process_and_store_document(url: str, html_content: str, openai_client: AsyncOpenAI, chroma_collection):
    """Process a document and store its chunks."""
    # Convert HTML to markdown-like text
    markdown_content = html_to_markdown(html_content)
    
    # Split into chunks
    chunks = chunk_text(markdown_content)
    print(f"Processing {len(chunks)} chunks for {url}")
    
    for i, chunk in enumerate(chunks):
        try:
            processed_chunk = await process_chunk(chunk, i, url, openai_client)
            await insert_chunk(processed_chunk, chroma_collection)
        except Exception as e:
            print(f"Error processing chunk {i} for {url}: {e}")
            traceback.print_exc()

def get_urls_from_sitemap(sitemap_url: str) -> List[str]:
    """Get URLs from a sitemap."""
    try:
        response = requests.get(sitemap_url)
        response.raise_for_status()

        root = ElementTree.fromstring(response.content)
        namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [loc.text for loc in root.findall(".//ns:loc", namespace)]

        print(f"Found {len(urls)} URLs in sitemap: {sitemap_url}")
        return urls
    except Exception as e:
        print(f"Error fetching sitemap: {e}")
        return []

async def crawl_url(url: str, openai_client: AsyncOpenAI, chroma_collection):
    """Crawl a single URL and process its content."""
    try:
        print(f"Crawling {url}...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Process the HTML content
        await process_and_store_document(url, response.text, openai_client, chroma_collection)
        return True
    except Exception as e:
        print(f"Error crawling {url}: {e}")
        traceback.print_exc()
        return False

async def crawl_parallel(urls: List[str], openai_api_key: Optional[str] = None, max_concurrent: int = 3):
    """Crawl multiple URLs in parallel with a concurrency limit."""
    if not urls:
        print("No URLs provided for crawling")
        return
    
    print(f"Starting to crawl {len(urls)} URLs")
    
    # Initialize OpenAI client
    api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OpenAI API key not provided")
        return
    
    openai_client = AsyncOpenAI(api_key=api_key)
    
    # Initialize ChromaDB collection
    chroma_collection = init_collection()
    
    # Set up semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_url(url):
        async with semaphore:
            return await crawl_url(url, openai_client, chroma_collection)
    
    # Process URLs in parallel with concurrency limit
    tasks = [process_url(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Count successful crawls
    successful = sum(1 for r in results if r is True)
    print(f"Successfully crawled {successful} out of {len(urls)} URLs")
