import socket
import random
import time
import json
import re
import requests
import os
import argparse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import colorama
from colorama import Fore, Style
import shutil
import subprocess  # For running shell commands

# Original configuration
cache = {}
WHITE = "\033[97m"
RED = "\033[91m"
GREEN = "\033[92m"
RESET = "\033[0m"

def autocorrect_json(file_path):
    if not os.path.exists(file_path):
        return

    # Read the content of the JSON file
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    # Attempt to fix common issues
    # Remove trailing commas
    corrected_content = re.sub(r',\s*}', '}', content)  # Remove trailing comma before closing brace
    corrected_content = re.sub(r',\s*]', ']', corrected_content)  # Remove trailing comma before closing bracket

    # Check if the file ends with the required JSON structure
    required_end = '        }\n    }\n}'
    if not corrected_content.strip().endswith(required_end):
        corrected_content = corrected_content.strip() + '\n' + required_end

    # Attempt to load the corrected JSON
    try:
        json.loads(corrected_content)
    except json.JSONDecodeError:
        print(f"Could not correct JSON in {file_path}. Manual correction needed.")
        return

    # Write the corrected content back to the file
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(corrected_content)
    print(f"Corrected JSON in {file_path}.")

def load_responses():
    autocorrect_json('inputs.json')
    autocorrect_json('responses.json')

    try:
        with open('inputs.json', 'r') as f:
            inputs = json.load(f)
    except FileNotFoundError:
        inputs = {"input": {}}
    
    try:
        with open('responses.json', 'r') as f:
            responses = json.load(f)
    except FileNotFoundError:
        responses = {"input": {}}

    return inputs['input'], responses['input']

# The rest of your existing code follows...

def save_input_response(inputs_dict, responses_dict, input_message, response_message):
    inputs_dict[input_message] = {"meaning": response_message}
    with open('inputs.json', 'w') as f:
        json.dump({"input": inputs_dict}, f, ensure_ascii=False, indent=4)

    responses_dict[response_message] = {"meaning": response_message}
    with open('responses.json', 'w') as f:
        json.dump({"input": responses_dict}, f, ensure_ascii=False, indent=4)

def find_random_starting_response(responses_dict):
    if responses_dict:
        return random.choice(list(responses_dict.values()))['meaning']
    return "Hello, how can I assist you?"

def clean_response(response):
    return re.sub(r'\s*[\d+]', '', response).strip()

def fetch_wikipedia_sentences(word):
    if word in cache:
        return cache[word]

    url = f"https://en.wikipedia.org/wiki/{word.capitalize()}"
    response = requests.get(url)
    
    if response.status_code == 200:
        if '(disambiguation)' in response.url:
            cache[word] = []
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all('p')
        sentences = []
        for paragraph in paragraphs:
            sentences.extend(re.split(r'(?<=[.!?]) +', paragraph.text))
        
        filtered_sentences = [clean_response(sentence) for sentence in sentences if word.lower() in sentence.lower()]
        
        filtered_sentences = [s for s in filtered_sentences if s.endswith('.') and not s.endswith(':')]
        cache[word] = filtered_sentences[:5]
        return cache[word]
    return []

def format_sentence(sentence):
    if '[' in sentence or ']' in sentence:
        return ""
    sentence = sentence.strip()
    if sentence and sentence.endswith('.') and not sentence.endswith(':'):
        return sentence[0].upper() + sentence[1:]

def enhanced_response_generation(input_words):
    try:
        ddg_response = requests.get(
            f"https://api.duckduckgo.com/?q={'+'.join(input_words)}&format=json&no_html=1",
            timeout=3
        )
        if ddg_response.status_code == 200:
            data = ddg_response.json()
            if data.get('AbstractText'):
                return data['AbstractText']
        
        wd_response = requests.get(
            f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={'+'.join(input_words)}&format=json&language=en",
            timeout=3
        )
        if wd_response.status_code == 200:
            data = wd_response.json()
            if data.get('search'):
                return data['search'][0].get('description')
    except:
        pass
    return None

def best_match_response(user_input, inputs_dict):
    max_match_count = 0
    best_response = None

    normalized_input = user_input.strip().lower().split()

    for key in inputs_dict.keys():
        current_response = inputs_dict[key]["meaning"]
        key_words = key.split()
        
        match_count = sum(1 for word in normalized_input if word in key_words)
        
        if match_count > max_match_count:
            max_match_count = match_count
            best_response = current_response

    return best_response

def create_backup():
    if not os.path.exists("killme"):
        os.makedirs("killme")
    shutil.copy("server_ai2.py", "killme/server_ai2.py")
    shutil.copy("client_ai2.py", "killme/client_ai2.py")

def list_functions():
    with open(__file__, 'r') as f:
        lines = f.readlines()
    functions = [line.strip().split()[1] for line in lines if line.startswith('def ')]
    return functions

def show_function_code(function_name):
    with open(__file__, 'r') as f:
        lines = f.readlines()
    
    in_function = False
    function_code = []
    
    for line in lines:
        if line.startswith(f'def {function_name}'):
            in_function = True
        if in_function:
            function_code.append(line)
            if line.strip() == '':
                break

    return ''.join(function_code)

def start_server():
    inputs_dict, responses_dict = load_responses()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('localhost', 5000))
    server.listen(1)
    print("server_ai2.py: Server is running and waiting for a connection...")

    conn, addr = server.accept()
    print(f"server_ai2.py: Connected to {addr}")

    conversation_history = []

    message = find_random_starting_response(responses_dict)
    conn.sendall(clean_response(message).encode('utf-8'))
    time.sleep(0.001)

    response_count = 0

    with ThreadPoolExecutor(max_workers=10) as executor:
        while True:
            try:
                response = conn.recv(1024).decode('utf-8')
                response = clean_response(response)
                print(f"{Fore.RED}[{Fore.RESET}>{Fore.RED}]: {GREEN}{response}")

                if response.lower() == "run programming console":
                    print("Running programming console...")
                    subprocess.run(["sudo", "bash", "use_coder.sh"], check=True)
                    continue
                
                if response.lower() == "backup":
                    create_backup()
                    print("Backup created in 'killme' folder.")
                    continue
                
                if response.lower() == "show functions":
                    functions = list_functions()
                    print("Available functions:")
                    for i, func in enumerate(functions, 1):
                        print(f"{i}. {func}")
                    
                    selected = int(input("Select a function to show: ")) - 1
                    if 0 <= selected < len(functions):
                        function_code = show_function_code(functions[selected])
                        print(f"Code for {functions[selected]}:\n{function_code}")
                    continue

                input_words = response.split()
                all_relevant_sentences = []

                results = list(executor.map(fetch_wikipedia_sentences, input_words))

                for sentences in results:
                    all_relevant_sentences.extend(sentences)

                formatted_sentences = [format_sentence(sentence) for sentence in all_relevant_sentences]
                formatted_sentences = [s for s in formatted_sentences if s]

                feedback = "Could you please rephrase or provide more context?"
                
                if formatted_sentences:
                    max_attempts = 3
                    for _ in range(max_attempts):
                        max_sentences = random.randint(1, 5)
                        selected = random.sample(
                            formatted_sentences,
                            min(max_sentences, len(formatted_sentences))
                        )
                        candidate = ' '.join(selected)
                        if candidate not in conversation_history:
                            feedback = candidate
                            conversation_history.append(feedback)
                            break
                    else:
                        enhanced = enhanced_response_generation(input_words)
                        feedback = enhanced if enhanced else feedback
                else:
                    enhanced = enhanced_response_generation(input_words)
                    if enhanced:
                        feedback = enhanced
                    else:
                        best_match = best_match_response(response, inputs_dict)
                        feedback = best_match if best_match else feedback

                save_input_response(inputs_dict, responses_dict, response, feedback)
                conn.sendall(clean_response(feedback).encode('utf-8'))

                response_count += 1
                if response_count % 10 == 0:
                    create_backup()

                if response.lower() in ['exit', 'quit']:
                    break
            except Exception as e:
                print(f"Error: {e}")
                break

    conn.close()
    server.close()

def start_user_mode():
    inputs_dict, responses_dict = load_responses()
    conversation_history = []
    
    if responses_dict:
        print("User mode activated. You can start typing your questions.")
    
    while True:
        response = input(f"{Fore.GREEN}[{Fore.RESET}<{Fore.GREEN}]: ")
        response = clean_response(response)

        if response.lower() == "run programming console":
            print("Running programming console...")
            subprocess.run(["sudo", "bash", "use_coder.sh"], check=True)
            continue
        
        if response.lower() == "backup":
            create_backup()
            print("Backup created in 'killme' folder.")
            continue

        if response.lower() == "show functions":
            functions = list_functions()
            print("Available functions:")
            for i, func in enumerate(functions, 1):
                print(f"{i}. {func}")
            
            selected = int(input("Select a function to show: ")) - 1
            if 0 <= selected < len(functions):
                function_code = show_function_code(functions[selected])
                print(f"Code for {functions[selected]}:\n{function_code}")
            continue

        best_match = best_match_response(response, inputs_dict)

        if best_match:
            feedback = best_match
        else:
            input_words = response.split()
            all_relevant_sentences = []

            with ThreadPoolExecutor(max_workers=10) as executor:
                results = list(executor.map(fetch_wikipedia_sentences, input_words))

            for sentences in results:
                all_relevant_sentences.extend(sentences)

            formatted_sentences = [format_sentence(sentence) for sentence in all_relevant_sentences]
            formatted_sentences = [s for s in formatted_sentences if s]

            if formatted_sentences:
                max_attempts = 3
                feedback = None
                for _ in range(max_attempts):
                    max_sentences = random.randint(1,5)
                    selected = random.sample(
                        formatted_sentences,
                        min(max_sentences, len(formatted_sentences))
                    )
                    candidate = ' '.join(selected)
                    if candidate not in conversation_history:
                        feedback = candidate
                        conversation_history.append(feedback)
                        break
                if feedback is None:
                    enhanced = enhanced_response_generation(input_words)
                    feedback = enhanced if enhanced else "No relevant response found"
            else:
                enhanced = enhanced_response_generation(input_words)
                feedback = enhanced if enhanced else "No relevant response found"

        print(f"{Fore.GREEN}[{Fore.RESET}>{Fore.GREEN}]:{Fore.RED} {feedback}")

        satisfied = input(f"{Fore.RED}Are you satisfied with this response? (y/n): ").lower()
        if satisfied == 'n':
            correct_response = input(f"{Fore.RED}Please provide the correct response: ")
            save_input_response(inputs_dict, responses_dict, response, correct_response)

        if response.lower() in ['exit', 'quit']:
            break

if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{Fore.RED}========={Fore.RESET} A L E X A N D R I A N {Fore.RED}=========")
    print(f"{Fore.GREEN} ------< {Fore.RESET}I N T E L L I G E N C E{Fore.GREEN} >------")

    parser = argparse.ArgumentParser(description='Run server or user mode.')
    parser.add_argument('-u', action='store_true', help='Activate user input mode')
    args = parser.parse_args()

    if args.u:
        start_user_mode()
    else:
        start_server()
