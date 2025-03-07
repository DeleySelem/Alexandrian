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
import subprocess
from collections import Counter

# Initialize colorama with custom colors
colorama.init(autoreset=True)
Fore.BLUE_DARK = '\033[34m'

HEXAGRAMS = [
    ("䷀", "The Creative"), ("䷁", "The Receptive"), ("䷂", "Difficulty at the Beginning"),
    ("䷃", "Youthful Folly"), ("䷄", "Waiting"), ("䷅", "Conflict"),
    ("䷆", "Army"), ("䷇", "Holding Together"), ("䷈", "Small Taming"),
    ("䷉", "Treading"), ("䷊", "Peace"), ("䷋", "Standstill"),
    ("䷌", "Fellowship"), ("䷍", "Great Possession"), ("䷎", "Modesty"),
    ("䷏", "Enthusiasm"), ("䷐", "Following"), ("䷑", "Work on the Decayed"),
    ("䷒", "Approach"), ("䷓", "Contemplation"), ("䷔", "Biting Through"),
    ("䷕", "Grace"), ("䷖", "Splitting Apart"), ("䷗", "Return"),
    ("䷘", "Innocence"), ("䷙", "Great Taming"), ("䷚", "Nourishment"),
    ("䷛", "Great Excess"), ("䷜", "Water"), ("䷝", "Fire"),
    ("䷞", "Clinging Fire"), ("䷟", "Lake"), ("䷠", "Mountain"),
    ("䷡", "Thunder"), ("䷢", "Wind"), ("䷣", "Water over Fire"),
    ("䷤", "Fire over Water"), ("䷥", "Abundance"), ("䷦", "Traveling"),
    ("䷧", "Wandering"), ("䷨", "Pushing Upward"), ("䷩", "Darkening of the Light"),
    ("䷪", "Family"), ("䷫", "Opposition"), ("䷬", "Obstruction"),
    ("䷭", "Deliverance"), ("䷮", "Decrease"), ("䷯", "Increase"),
    ("䷰", "Breakthrough"), ("䷱", "Coming to Meet"), ("䷲", "Gathering"),
    ("䷳", "Pressing Onward"), ("䷴", "Well"), ("䷵", "Revolution"),
    ("䷶", "Cauldron"), ("䷷", "Shock"), ("䷸", "Gentle"),
    ("䷹", "Joyous"), ("䷺", "Dispersing"), ("䷻", "Limiting"),
    ("䷼", "Inner Truth"), ("䷽", "Small Excess"), ("䷾", "After Completion"),
    ("䷿", "Before Completion")
]

cache = {}

class HexagramGrid:
    def __init__(self):
        self.rows = []
        self.color_map = {"red": Fore.RED, "yellow": Fore.YELLOW, "green": Fore.GREEN}
        self.word_bank = []
        self.init_word_bank()
        self.init_grid()

    def init_word_bank(self):
        if os.path.exists('conversation.log'):
            with open('conversation.log', 'r') as f:
                text = f.read().lower()
                self.word_bank = re.findall(r'\w+', text)

    def init_grid(self):
        hexagrams = random.sample(HEXAGRAMS, 64)
        for i in range(8):
            row = []
            for j in range(8):
                symbol, name = hexagrams[i*8 + j]
                row.append({
                    "symbol": symbol,
                    "name": name,
                    "color": random.choice(list(self.color_map.keys())),
                    "position": (i, j),
                    "lines": [self.create_line() for _ in range(6)]
                })
            self.rows.append(row)

    def create_line(self):
        return {
            'state': 'closed' if random.random() < 0.5 else 'open',
            'word': random.choice(self.word_bank) if self.word_bank else ""
        }

    def update_based_on_premonition(self, is_match):
        hexagram = random.choice(random.choice(self.rows))
        line_idx = random.randint(0, 5)
        
        if is_match:
            hexagram['lines'][line_idx]['state'] = 'closed'
        else:
            self.open_line(hexagram, line_idx)
        
        self.shuffle_positions()
        self.rebuild_grid()

    def open_line(self, hexagram, line_idx):
        hexagram['lines'][line_idx]['state'] = 'open'
        neighbors = self.get_neighbors(hexagram['position'])
        closed_words = [line['word'] for n in neighbors for line in n['lines'] if line['state'] == 'closed']
        if closed_words:
            hexagram['lines'][line_idx]['word'] = random.choice(closed_words)

    def get_neighbors(self, pos):
        x, y = pos
        return [self.rows[x+dx][y+dy] for dx, dy in [(-1,-1), (-1,0), (-1,1),
                (0,-1),          (0,1),
                (1,-1),  (1,0),  (1,1)] if 0 <= x+dx < 8 and 0 <= y+dy < 8]

    def shuffle_positions(self):
        all_hexagrams = [h for row in self.rows for h in row]
        random.shuffle(all_hexagrams)
        self.rows = [all_hexagrams[i*8:(i+1)*8] for i in range(8)]

    def rebuild_grid(self):
        new_rows = [[None for _ in range(8)] for _ in range(8)]
        for row in self.rows:
            for hexagram in row:
                x, y = hexagram["position"]
                new_rows[x][y] = hexagram
        self.rows = new_rows

    def display(self):
        for row in self.rows:
            line = []
            for hexagram in row:
                color = self.color_map[hexagram["color"]]
                symbol = hexagram["symbol"]
                lines = ''.join(['-' if l['state'] == 'closed' else '○' for l in hexagram['lines']])
                line.append(f"{color}{symbol} {lines}{Style.RESET_ALL}")
            print("  ".join(line))

def clean_response(response):
    return re.sub(r'\s*[\d+]', '', response).strip()

def autocorrect_json(file_path):
    if not os.path.exists(file_path):
        return
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    corrected_content = re.sub(r',\s*}', '}', content)
    corrected_content = re.sub(r',\s*]', ']', corrected_content)
    required_end = '        }\n    }\n}'
    if not corrected_content.strip().endswith(required_end):
        corrected_content = corrected_content.strip() + '\n' + required_end
    try:
        json.loads(corrected_content)
    except json.JSONDecodeError:
        print(f"Could not correct JSON in {file_path}. Manual correction needed.")
        return
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(corrected_content)

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

def save_input_response(inputs_dict, responses_dict, input_message, response_message):
    inputs_dict[input_message] = {"meaning": response_message}
    with open('inputs.json', 'w') as f:
        json.dump({"input": inputs_dict}, f, ensure_ascii=False, indent=4)
    responses_dict[response_message] = {"meaning": response_message}
    with open('responses.json', 'w') as f:
        json.dump({"input": responses_dict}, f, ensure_ascii=False, indent=4)

def fetch_wikipedia_sentences(word):
    global cache
    if word in cache:
        return cache[word]
    try:
        url = f"https://en.wikipedia.org/wiki/{word.capitalize()}"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            if '(disambiguation)' in response.url:
                return []
            soup = BeautifulSoup(response.content, 'html.parser')
            paragraphs = soup.find_all('p')
            sentences = []
            for paragraph in paragraphs:
                sentences.extend(re.split(r'(?<=[.!?]) +', paragraph.text))
            filtered = [clean_response(s) for s in sentences if word.lower() in s.lower()]
            cache[word] = [s for s in filtered if s.endswith('.') and not s.endswith(':')][:5]
            return cache[word]
    except:
        return []

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
    except:
        pass
    return None

def best_match_response(user_input, inputs_dict):
    user_words = set(user_input.strip().lower().split())
    best_score = 0
    best_response = None
    for key, value in inputs_dict.items():
        key_words = set(key.lower().split())
        score = len(user_words & key_words)
        if score > best_score:
            best_score = score
            best_response = value["meaning"]
    return best_response
def generate_premonitions(hex_grid):
    if not os.path.exists('conversation.log'):
        return []
    try:
        with open('conversation.log', 'r') as f:
            lines = f.readlines()[-6:]
        words = [re.findall(r'\w+', line.split(": ", 1)[1].lower()) for line in lines if ": " in line]
        flat_words = [word for sublist in words for word in sublist]
        
        premonitions = []
        for word in flat_words:
            same_color_hexagrams = [
                h for row in hex_grid.rows 
                for h in row if h['color'] == random.choice(list(hex_grid.color_map.keys()))
            ]
            for hexagram in same_color_hexagrams:
                # Construct a base sentence that incorporates the word found
                sentence = f"I sense that {word} will come up in our discussion."
                
                # Check if there are open lines in the current hexagram
                if any(line['state'] == 'open' for line in hexagram['lines']):
                    # Borrow words from closed lines of neighboring hexagrams
                    for line in hexagram['lines']:
                        if line['state'] == 'open':
                            neighbors = hex_grid.get_neighbors(hexagram['position'])
                            closed_words = [
                                neighbor['lines'][line_idx]['word'] 
                                for neighbor in neighbors 
                                for line_idx in range(6) 
                                if neighbor['lines'][line_idx]['state'] == 'closed'
                            ]
                            if closed_words:
                                sentence = f"I think the user will mention {random.choice(closed_words)}."
                                break
                premonitions.append(sentence)

        return premonitions[:3]  # Return a maximum of 3 premonitions
    except Exception as e:
        print(f"Error generating premonitions: {e}")
        return []

def start_user_mode():
    inputs_dict, responses_dict = load_responses()
    hex_grid = HexagramGrid()
    print("Hexagram Interface Initialized\n")
    hex_grid.display()

    randomized_starts = [
        "I think the user is going to speak about",
        "I am sure my user is about to",
        "Next the user asks me about",
        "Is the user trying to explain",
        "Coming next"
    ]

    while True:
        try:
            # Get user input
            user_input = input(f"\n{Fore.GREEN}Your Query: ").strip()
            if not user_input:
                continue

            # Log input
            with open('conversation.log', 'a') as f:
                f.write(f"User: {user_input}\n")

            # Show thinking process
            print(f"\n{Fore.BLUE_DARK}Processing Query:")
            with ThreadPoolExecutor(max_workers=4) as executor:
                wiki_results = list(executor.map(fetch_wikipedia_sentences, user_input.split()))
            
            secondary_outputs = []
            for result in wiki_results:
                if result:  # Check if result is not None
                    for sentence in result[:3]:
                        cleaned = clean_response(sentence)
                        if cleaned:
                            print(f"{Fore.BLUE_DARK}>> {cleaned}")
                            secondary_outputs.append(cleaned)
                            time.sleep(0.3)

            # Generate response
            response = enhanced_response_generation(user_input.split()) or \
                      best_match_response(user_input, inputs_dict) or \
                      "Could you please rephrase your question?"

            # Show main response in bold
            print(f"\n{Fore.GREEN}\033[1mResponse: {response}\033[0m")
            with open('conversation.log', 'a') as f:
                f.write(f"[>>>]: {response}\n")

            # Generate and show premonitions
            premonitions = generate_premonitions(hex_grid)
            print(f"\n{Fore.CYAN}Future:")
            any_match = False
            for p in premonitions:
                match = p in response.lower()
                print(f"{Fore.CYAN}>> {p} {'✓' if match else '✗'}")
                hex_grid.update_based_on_premonition(match)
                any_match = any_match or match

            # Update grid display
            print("\nEmotional logic Grid:")
            hex_grid.display()

            # User satisfaction check
            satisfied = input("\nWas this response helpful? (y/n): ").lower()
            if satisfied == 'n':
                feedback_response = input("Please provide appropriate response for this input: ")
                # Save the feedback response for the specific user input
                inputs_dict[user_input] = {"meaning": feedback_response}
                with open('inputs.json', 'w') as f:
                    json.dump({"input": inputs_dict}, f, ensure_ascii=False, indent=4)
                print(f"{Fore.YELLOW}Thank you for your feedback. I will remember that response!")

            if user_input.lower() in ['exit', 'quit']:
                break

        except KeyboardInterrupt:
            print(f"\n{Fore.RED}Session Ended")
            break
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run in user mode')
    parser.add_argument('-u', action='store_true', help='User interaction mode')
    args = parser.parse_args()

    if args.u:
        start_user_mode()   
