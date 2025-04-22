# Company Profile & ESG Policy Generator 🌱

A Streamlit application that crawls company websites, analyzes company information, and generates tailored ESG (Environmental, Social, and Governance) policies.

## Features

- **Website Crawler**: Crawl company websites to extract relevant information
- **Company Profile Analysis**: Extract mission, vision, values, and objectives
- **ESG Policy Generation**: Generate tailored ESG policies based on company profile
- **Policy Alignment Analysis**: Assess how well the generated policies align with company values

## Deployment on Streamlit Cloud

1. Fork this repository
2. Log in to [Streamlit Cloud](https://streamlit.io/cloud)
3. Click on "New app" and select this repository
4. Set the main file path to `app.py`
5. Configure the following secrets in Streamlit Cloud settings:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `LLM_MODEL`: The OpenAI model to use (e.g., "gpt-4-0125-preview")

## Local Development

### Prerequisites

- Python 3.9+
- Pip

### Setup

1. Clone the repository
```bash
git clone https://github.com/Miguelramirez004/esg-policy-generator.git
cd esg-policy-generator
```

2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with the following variables
```
OPENAI_API_KEY=your_openai_api_key
LLM_MODEL=gpt-4-0125-preview
```

5. Run the application
```bash
streamlit run app.py
```

## Usage Guide

1. **Crawler Tab**: Input company website URLs to crawl and extract information
2. **ESG Parameters Tab**: Upload or configure ESG parameters using the Excel template
3. **Company Profile Tab**: Extract and view the company profile
4. **ESG Policies Tab**: Generate ESG policies based on the profile and parameters
5. **Alignment Analysis Tab**: Analyze the alignment between company values and policies

## Data Storage

The application uses ChromaDB to store document embeddings locally. The database is stored in a `chroma_db` directory in the application root.

## License

MIT
