#!/bin/bash

# coding_ai_setup.sh
# Modified version for Kali Linux/Externally managed environments

set -e
set -x

# Check requirements
command -v python3 >/dev/null 2>&1 || { echo >&2 "Python 3 required"; exit 1; }
python3 -m venv --help >/dev/null 2>&1 || { echo >&2 "python3-venv required"; exit 1; }

# Create project structure
mkdir -p local_codegen_ai
cd local_codegen_ai

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies using venv pip
pip install transformers torch black

# Download and save model using venv python
venv/bin/python - <<END
from transformers import AutoTokenizer, AutoModelForCausalLM
model_name = "Salesforce/codegen-350M-mono"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)
model.save_pretrained("./model")
tokenizer.save_pretrained("./model")
END

# Create the AI assistant script with venv shebang
cat > local_codegen_ai.py <<'END'
#!/usr/bin/env python3

import black
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM

class LocalCodingAI:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained("./model")
        self.model = AutoModelForCausalLM.from_pretrained("./model")
        self.generator = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            device=-1
        )
    
    def generate(self, prompt, max_length=200, temperature=0.7):
        generated = self.generator(
            prompt,
            max_length=max_length,
            temperature=temperature,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id
        )
        return self._format_code(generated[0]['generated_text'])
    
    def _format_code(self, code):
        try:
            return black.format_str(code, mode=black.FileMode())
        except:
            return code

if __name__ == "__main__":
    ai = LocalCodingAI()
    print("\nLocal Coding AI (type 'quit' to exit)")
    while True:
        try:
            prompt = input("\nPrompt: ")
            if prompt.lower() in ['quit', 'exit']:
                break
            print("\n" + ai.generate(prompt))
        except KeyboardInterrupt:
            break
END

# Make it executable
chmod +x local_codegen_ai.py

# Deactivate virtual environment
deactivate

# Instructions
echo -e "\n\nSetup complete! Run your local coding AI with:"
echo -e "cd local_codegen_ai && source venv/bin/activate && ./local_codegen_ai.py"
echo -e "Or for one-time execution:"
echo -e "cd local_codegen_ai && ./venv/bin/python local_codegen_ai.py"
