from flask import Flask, request, render_template
from azure.storage.blob import BlobServiceClient
from azure.cosmos import CosmosClient
from openai import AzureOpenAI
import os
import PyPDF2
import io
import uuid
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

blob_service_client = BlobServiceClient.from_connection_string(os.getenv("AZURE_BLOB_CONNECTION_STRING"))
blob_container_client = blob_service_client.get_container_client(os.getenv("AZURE_BLOB_CONTAINER_NAME"))

cosmos_client = CosmosClient(os.getenv("COSMOS_ENDPOINT"), os.getenv("COSMOS_KEY"))
cosmos_database = cosmos_client.get_database_client(os.getenv("COSMOS_DATABASE_NAME"))
cosmos_container = cosmos_database.get_container_client(os.getenv("COSMOS_CONTAINER_NAME"))

api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
deployment_name = os.getenv("DEPLOYMENT_NAME")
client = AzureOpenAI(api_key=api_key, api_version="2024-02-01", azure_endpoint=azure_endpoint)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'fetch':
            user_id = request.form['user_id']

            # Fetch user data from Cosmos DB
            query = f"SELECT * FROM c WHERE c.userId = '{user_id}'"
            items = list(cosmos_container.query_items(query=query, enable_cross_partition_query=True))
            if not items:
                return "User data not found", 404
            user_data = items[0]

        elif action == 'add':
            user_data = {
                'userId': request.form['user_id_add'],
                'income': int(request.form['income']),
                'expenses': int(request.form['expenses']),
                'assets': {
                    'savings': int(request.form['savings']),
                    'investments': int(request.form['investments'])
                },
                'liabilities': {
                    'loans': int(request.form['loans']),
                    'credit_card_debt': int(request.form['credit_card_debt'])
                },
                'id': str(uuid.uuid4())
            }
            cosmos_container.create_item(body=user_data)

        # Fetch financial document from Blob Storage
        blob_name = "INVESTMENT_STRATEGIES_ijariie20675.pdf"  
        blob_client = blob_container_client.get_blob_client(blob_name)
        blob_data = blob_client.download_blob().readall()

        # Read PDF content
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(blob_data))
        financial_plan = ""
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            financial_plan += page.extract_text()

        # Generate financial advice using Azure OpenAI
        prompt = (
            f"User Data:\n"
            f"{user_data}\n\n"
            f"Financial Plan:\n"
            f"{financial_plan}\n\n"
            f"Please generate personalized financial advice based on the above information, considering the user's "
            f"income, expenses, savings, and any other financial details provided. The advice should be actionable and "
            f"tailored to the user's specific financial situation."
        )

        messages = [
            {"role": "system", "content": "You are a helpful financial advisor."},
            {"role": "user", "content": prompt}
        ]
        response = client.chat.completions.create(
            model=deployment_name,
            messages=messages
        )
        financial_advice = response.choices[0].message.content.strip()

        return render_template('index.html', financial_advice=financial_advice)

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
