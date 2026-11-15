import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY") # your own secret name if different

client = Groq()                          # reads GROQ_API_KEY
MODEL = "openai/gpt-oss-120b"       # if "model not found", check console.groq.com for the current name

if not groq_api_key or groq_api_key == "paste_your_key_here":
    raise SystemExit("GROQ_API_KEY not found.\nCopy .env.example to .env and paste your Groq key in it.")

