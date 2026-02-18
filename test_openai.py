import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

endpoint   = os.getenv("AZURE_OPENAI_ENDPOINT")
api_key    = os.getenv("AZURE_OPENAI_API_KEY")
api_ver    = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

assert endpoint and api_key and deployment, "Missing Azure OpenAI env vars."

client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=api_key,
    api_version=api_ver
)

resp = client.chat.completions.create(
    model=deployment,
    messages=[{"role": "user", "content": "Reply with: OK from Azure OpenAI"}],
    temperature=0
)
print(resp.choices[0].message.content)
