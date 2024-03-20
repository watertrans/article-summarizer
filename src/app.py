import logging
import json
import requests
import sys
import os
from azure.data.tables import TableClient
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger_name": record.name,
            "module": record.module,
            "line_number": record.lineno,
            "function_name": record.funcName
        }

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record, ensure_ascii=False)

def setup_logger(logger_name):
    """
    This function sets and returns the logger.
    """

    json_formatter = JSONFormatter()

    # WARNING and lower level logs are output to stdout
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.NOTSET)
    stdout_handler.setFormatter(json_formatter)
    stdout_handler.addFilter(lambda record: record.levelno <= logging.WARNING)

    # ERROR and CRITICAL level logs are output to stderr
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)
    stderr_handler.setFormatter(json_formatter)

    logger = logging.getLogger(logger_name)

    # The log output level can be controlled by environment variables. The default and invalid value is INFO.
    log_level_str = os.getenv("LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_str.upper(), None)
    if not isinstance(log_level, int):
        log_level = logging.INFO
    logger.setLevel(log_level)
    logger.addHandler(stdout_handler)
    logger.addHandler(stderr_handler)

    return logger

def get_content(url):
    """
    Retrieves and returns the HTML content of the specified URL. If an error occurs, an empty string is returned.
    """

    try:
        response = requests.get(url, timeout=10)
        if response.status_code >= 500:
            logger.warning(f"An error has occurred on the server: { response.status_code } { response.reason }")
            return ""
        elif response.status_code >= 400:
            logger.warning(f"An error has occurred on the client: { response.status_code } { response.reason }")
            return ""
        elif response.status_code >= 300:
            logger.warning(f"Unexpected 3xx status code responded: { response.status_code } { response.reason }")
            return ""
    except requests.Timeout:
        logger.warning("Request timed out")
        return ""
    except Exception as e:
        logger.error("Unknown error occurred", exc_info=True)
        return ""
    
    return response.content

def get_article(content):
    """
    Extracts the text of an article from the specified HTML content and returns an array of text chunks. HTML content without an article tag return an empty array.
    """
    
    soup = BeautifulSoup(content, 'html.parser')
    article_content = soup.find('article')

    if article_content is None:
        return []

    h1 = article_content.find('h1')

    if h1 is not None:
        h1_text = h1.get_text()
        h1.decompose()

    # remove unneeded elements
    for tag in ["img", "footer", "source", "style", "picture", "figure"]:
        for t in article_content.find_all(tag):
            t.decompose()

    # adding quotation marks to text within code or pre tags
    code_tags = soup.find_all(['code', 'pre'])
    for code_tag in code_tags:
        if '\n' in code_tag.text.strip():
            code_tag.string = f"\n'''code\n{code_tag.text.strip()}\n'''\n"

    # conversation tokens are capped. Here the whole thing is chunked in 2000 character units
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000, 
        chunk_overlap=0, 
        separators=[',', '.', '、', '。']
    )

    text_chunks = text_splitter.split_text(article_content.get_text())

    if h1_text is not None:
        text_chunks.insert(0, f"title:\n{h1_text}\narticle:\n")

    return text_chunks

def get_summarize(url):
    """
    Generates and returns a summary of the article at the specified URL.
    """

    api_key = os.getenv("API_KEY")
    logger.debug(f"url: {url}")

    content = get_content(url)

    if content == "":
        logger.warning(f"Failed to retrieve the HTML content of the following URL: {url}")
        return ""

    text_chunks = get_article(content)

    if len(text_chunks) == 0:
        logger.warning(f"The HTML content of the following URL does not contain an article tag: {url}")
        return ""

    client = OpenAI(api_key=api_key)
    messages = [{"role": "system", "content": """
        You are a professional editor. The text to be entered is an article about technology.
        Please summarize the article in 1000 words or less. Output should be in Japanese.
        Please adhere to the following constraints:
        - Do not omit the title of the article at the beginning.
        - Do not omit important keywords.
        - Do not change the meaning of the text.
        - Do not use fictitious expressions or words.
    """}]
    for text_chunk in text_chunks:
        logger.debug(f"text_chunk: {text_chunk}")
        messages.append({
            "role": "user", "content": text_chunk
        })

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        logger.debug(f"result: {response.choices[0].message.content}")
        return response.choices[0].message.content
    except Exception as e:
        logger.error("Unknown error occurred", exc_info=True)
        return ""

def write_history(partition_key, row_key, url, content):
    """
    Writes the summarized results to the history table.
    """
    entity = {
        "PartitionKey": partition_key,
        "RowKey": row_key,
        "url": url,
        "content": content
    }
    try:
        table_client.upsert_entity(entity)
    except Exception as e:
        logger.error("Write to history table failed", exc_info=True)

def read_history(partition_key, row_key, url):
    """
    Reads summarized results from the history table.
    """
    try:
        entity = table_client.get_entity(partition_key=partition_key, row_key=row_key)
        return entity
    except Exception as e:
        logger.info(f"No previous summary records available: {url}")
        return None

load_dotenv()
logger = setup_logger("Article Summarizer")
connection_string = os.getenv("STORAGE_CONNECTION_STRING")
table_name = 'summarizer'
table_client = TableClient.from_connection_string(connection_string, table_name)

partition_key = "devblogs.microsoft.com"
row_key = "dev-tunnels-a-game-changer-for-mobile-developers"
url = "https://devblogs.microsoft.com/dotnet/dev-tunnels-a-game-changer-for-mobile-developers/"

history = read_history(partition_key, row_key, url)

if history is not None:
    exit(0)

summarized_content = get_summarize(url)

write_history(partition_key, row_key, url, summarized_content)

print(summarized_content)

