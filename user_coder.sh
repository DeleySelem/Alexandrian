# Make script executable
chmod +x coding_ai_setup.sh

# Run setup
bash coding_ai_setup.sh

# Run the AI (from project directory)
cd local_codegen_ai
source venv/bin/loal_codegen_ai && ./local_codegen_ai.py
