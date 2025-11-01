from dotenv import load_dotenv
load_dotenv('api.env')

from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-4o",
    input=[
        {
            "role": "user",
            "content": "대한민국의 수도는 어디야?"
        }
    ]
)

print(response.output_text)