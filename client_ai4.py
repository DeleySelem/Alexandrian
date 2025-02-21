import socket
import json
import random
import requests
import os
import re
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
import colorama
from colorama import Fore, Style

# Global configurations
CACHE = {}
LAST_RESPONSES = deque(maxlen=3)
HISTORY = deque(maxlen=5)
STOPWORDS = {"it", "to", "so", "a", "the", "about", "is", "of", "in", "on"}
QUESTION_WORDS = {"what", "where", "when", "why", "how", "who", "which", "tell", "explain", "describe"}

# ANSI colors
WHITE = "\033[97m"
RED = "\033[91m"
GREEN = "\033[92m"
RESET = "\033[0m"

def load_responses():
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

def save_input_response(inputs_dict, responses_dict, input_message, response_message):
    inputs_dict[input_message] = {"meaning": input_message}
    with open('inputs.json', 'w') as f:
        json.dump({"input": inputs_dict}, f, ensure_ascii=False, indent=4)

    responses_dict[response_message] = {"meaning": response_message}
    with open('responses.json', 'w') as f:
        json.dump({"input": responses_dict}, f, ensure_ascii=False, indent=4)

# ------------------- Data Sources -------------------
def fetch_wikipedia(word):
    if word in CACHE:
        return CACHE[word]
    
    url = f"https://en.wikipedia.org/wiki/{word.capitalize()}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            paragraphs = soup.find_all('p')
            sentences = [p.get_text() for p in paragraphs]
            processed = process_sentences(sentences, word)
            CACHE[word] = processed
            return processed
    except:
        pass
    return []

def fetch_duckduckgo(word):
    url = "https://api.duckduckgo.com/"
    params = {"q": word, "format": "json", "no_html": 1}
    try:
        data = requests.get(url, params=params, timeout=5).json()
        return [data.get('AbstractText', "")] if data.get('AbstractText') else []
    except:
        return []

def fetch_wikidata(word):
    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbsearchentities",
        "search": word,
        "format": "json",
        "language": "en"
    }
    try:
        data = requests.get(url, params=params, timeout=5).json()
        return [item.get('description', "") for item in data.get('search', [])[:3]]
    except:
        return []

# ------------------- Core Logic -------------------
def is_meaningless(sentence, keyword):
    if re.match(rf'^{keyword}[,\s]*(?:{keyword}[,\s]*)+or {keyword}$', sentence, re.I):
        return True
    return len(sentence.split()) < 5 or sentence.count(' ') < 3

def process_sentences(sentences, keyword):
    filtered = []
    for s in sentences:
        s = re.sub(r'\s*\[\d+\]', '', s.strip())
        s = re.sub(r'\s+', ' ', s)
        if (s and s[0].isupper() and s.endswith('.') 
            and not is_meaningless(s, keyword)
            and keyword.lower() in s.lower()):
            filtered.append(s)
    return filtered[:10]

def score_sentence(sentence, keyword):
    keyword = keyword.lower()
    words = sentence.lower().split()
    try:
        pos = words.index(keyword)
    except ValueError:
        return 0
    
    position_score = 1.5 - (pos / len(words))
    starts_with = 3 if words[0] == keyword else 0
    length_score = min(len(words)/30, 1)
    return position_score + starts_with + length_score

def resolve_references(input_text):
    if not HISTORY:
        return ""
    last_message = HISTORY[-1].lower()
    words = [w for w in re.findall(r'\b\w+\b', last_message) 
            if w not in STOPWORDS and len(w) > 2]
    return max(set(words), key=words.count) if words else ""

def extract_keywords(input_text):
    input_text = input_text.lower()
    
    # Detect questions
    if any(input_text.startswith(w) for w in QUESTION_WORDS) or '?' in input_text:
        return [w for w in re.findall(r'\b\w+\b', input_text) 
               if w not in QUESTION_WORDS and w not in STOPWORDS]
    
    # Extract meaningful words
    keywords = [w for w in re.findall(r'\b\w+\b', input_text) 
               if w not in STOPWORDS and len(w) > 2]
    
    # Resolve pronouns using history
    if not keywords and HISTORY:
        resolved = resolve_references(input_text)
        if resolved:
            keywords.append(resolved)
    
    return keywords[:3]

def generate_response(input_text):
    HISTORY.append(input_text)
    keywords = extract_keywords(input_text)
    
    # Fetch from all sources
    combined = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for word in keywords:
            for source in [fetch_wikipedia, fetch_duckduckgo, fetch_wikidata]:
                futures.append(executor.submit(source, word))
        
        for future in futures:
            combined.extend(future.result())

    # Score and select sentences
    scored = []
    for s in combined:
        for kw in keywords:
            if kw.lower() in s.lower():
                scored.append((score_sentence(s, kw), s))
    
    scored.sort(reverse=True, key=lambda x: x[0])
    candidates = list({s for _, s in scored if s.strip()})
    
    # Select non-repeating response
    for candidate in candidates:
        if candidate not in LAST_RESPONSES:
            LAST_RESPONSES.append(candidate)
            return candidate[:500]
    
    return "Could you please rephrase or provide more context?"

# ------------------- Client Code -------------------
def start_client():
    inputs_dict, responses_dict = load_responses()
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(('localhost', 5000))
    print(f"{Fore.GREEN}Connected to server. Start chatting!{RESET}")

    while True:
        try:
            message = client.recv(4096).decode('utf-8').strip()
            if not message:
                continue
            
            print(f"\n{Fore.RED}Server:{RESET} {message}")
            
            # Generate response using same logic as server
            response = generate_response(message)
            print(f"{Fore.GREEN}You:{RESET} {response}")
            
            save_input_response(inputs_dict, responses_dict, message, response)
            client.sendall(response.encode('utf-8'))

            if message.lower() in ['exit', 'quit']:
                break

        except Exception as e:
            print(f"Error: {e}")
            break

    client.close()

if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{Fore.RED}========= AI Conversation Client =========")
    start_client()
