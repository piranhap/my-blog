import asyncio
import os
import re
import subprocess

import g4f
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt
from zhipuai import ZhipuAI

# Enable debug logging if needed
g4f.debug.logging = True

# Get target languages from the action input
LAGNS = os.environ.get('LANGS').split(',')
ZHIPUAI_API_KEY = os.environ.get('ZHIPUAI_API_KEY', '')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

zhipuai_client = ZhipuAI(api_key=ZHIPUAI_API_KEY)
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


def run_shell_command(command: str) -> tuple:
    result = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return result.returncode, result.stdout, result.stderr


async def async_zhipuai(messages: list):
    response = zhipuai_client.chat.asyncCompletions.create(
        model="glm-4-flash",
        messages=messages,
    )
    task_id = response.id

    task_status = ''
    while task_status not in ('SUCCESS', 'FAILED'):
        result_response = zhipuai_client.chat.asyncCompletions.retrieve_completion_result(
            id=task_id
        )
        task_status = result_response.task_status
        await asyncio.sleep(0.5)
    return result_response


@retry(stop=stop_after_attempt(5))
async def chat_completion(query: str) -> str:
    response = ''
    messages = [{"role": "user", "content": query}]
    if ZHIPUAI_API_KEY:
        print('Using zhipuai.')
        response = await async_zhipuai(messages)
        response = response.choices[0].message.content
    elif OPENAI_API_KEY:
        print('Using openai.')
        response = await openai_client.chat.completions.create(
            model='gpt-4o',
            messages=messages,
        )
        response = response.choices[0].message.content
    else:
        print('Using g4f.')
        response = await g4f.ChatCompletion.create_async(
            model="gpt-4o",
            messages=messages,
        )
    if not response:
        raise Exception("Translation failed.")
    return response


async def translate_content(content: str, output_lang: str) -> str:
    # Modify output language text as needed
    if output_lang == 'es':
        output_lang = 'Spanish Version'
    elif output_lang == 'en':
        output_lang == 'English Version'
 
    translate_query = (
        f'Translate the following markdown content to [{output_lang}], '
        'preserving all formatting, code blocks, and line breaks. '
        'Only output the translated markdown content without additional commentary:\n'
        '--------------------------------\n'
        f'{content}\n'
        '--------------------------------\n'
    )
    response = await chat_completion(translate_query)
    print(f'Translation Response:\n{response}')
    return response


def extract_prefix(filename: str) -> str:
    """Extract file prefix path (e.g., directory)"""
    pattern = re.compile(r'(.*\/).*')
    match = pattern.match(filename)
    return match.group(1) if match else ''


async def main():
    # Prevent running on auto-commit changes
    git_last_commit_message = "git show -s --format=%s"
    last_commit_message = run_shell_command(git_last_commit_message)[1].strip()
    if last_commit_message == "Auto-translate content":
        print('Auto translated, skipping...')
        return

    # List modified files in the last commit (or adjust as needed)
    git_diff_command = "git diff --name-only HEAD~1 HEAD"
    return_code, stdout, _ = run_shell_command(git_diff_command)
    if return_code != 0:
        print('No files changed.')
        return

    modified_files = stdout.split("\n")
    tasks = []

    # Process only Markdown files in content/en/
    for file in modified_files:
        if not file.startswith("content/en/") or not file.endswith(".md"):
            continue

        print(f'Processing changed file: {file}')
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()

        # Define a coroutine for each target language
        async def process_translation(output_lang: str, source_file: str, source_content: str):
            # Determine the output path: replace content/en with content/es
            output_file = source_file.replace("content/en/", "content/es/")
            # Ensure the directory exists:
            output_dir = extract_prefix(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            translated_content = await translate_content(source_content, output_lang)
            with open(output_file, "w", encoding="utf-8") as out_f:
                out_f.write(translated_content)
            print(f"Translated content written to {output_file}")

        # Add tasks for each language from the input (e.g., "es")
        for lang in LAGNS:
            tasks.append(process_translation(lang, file, content))

    if tasks:
        await asyncio.gather(*tasks)
    else:
        print("No relevant files changed for translation.")

if __name__ == "__main__":
    asyncio.run(main())

