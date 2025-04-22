from __future__ import annotations

from dataclasses import dataclass
from dotenv import load_dotenv
from litellm import AsyncOpenAI
import os
import json
from typing import List, Dict, Any, Optional
from chromadb.api.models.Collection import Collection

load_dotenv()

llm = os.getenv("LLM_MODEL", "gpt-4-0125-preview")

@dataclass
class CompanyProfileDeps:
    collection: Collection
    openai_client: AsyncOpenAI

system_prompt = """
You are an expert company profile and ESG policy analyst. Your role is to:
1. Extract and analyze company information from their documentation
2. Identify key company values, mission, and objectives
3. Generate appropriate ESG policies based on company context and provided parameters
4. Ensure alignment between company values and suggested policies

Always cite specific sources when providing information and be clear about what is directly stated versus inferred.
"""

async def get_embedding(text: str, openai_client: AsyncOpenAI) -> List[float]:
    """Get embedding vector from OpenAI."""
    try:
        response = await openai_client.embeddings.create(
            model="text-embedding-3-small", input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return [0] * 1536

async def retrieve_company_info(deps: CompanyProfileDeps, query: str) -> str:
    """Retrieve relevant company information documentation."""
    try:
        query_embedding = await get_embedding(query, deps.openai_client)
        
        results = deps.collection.query(
            query_embeddings=[query_embedding],
            n_results=5,
            include=["documents", "metadatas"]
        )

        if not results["documents"][0]:
            return "No relevant company information found."

        formatted_chunks = []
        for doc, metadata in zip(results["documents"][0], results["metadatas"][0]):
            chunk_text = f"""
# {metadata['title']}

{doc}

Source: {metadata['url']}
Last Updated: {metadata.get('crawled_at', 'N/A')}
"""
            formatted_chunks.append(chunk_text)

        return "\n\n---\n\n".join(formatted_chunks)

    except Exception as e:
        print(f"Error retrieving company information: {e}")
        return f"Error retrieving information: {str(e)}"

async def extract_company_profile(deps: CompanyProfileDeps) -> dict:
    """Extract company profile information including mission, vision, and objectives."""
    try:
        # Query for company profile information
        profile_query = "about us mission vision values objectives company profile"
        documentation = await retrieve_company_info(deps, profile_query)
        
        analysis_prompt = f"""
        Extract and analyze company profile information from this documentation:
        {documentation}
        
        Return a JSON object with:
        1. Company Name
        2. Mission Statement (if found)
        3. Vision Statement (if found)
        4. Core Values
        5. Key Objectives
        6. Company Overview
        7. Sources Used
        """
        
        response = await deps.openai_client.chat.completions.create(
            model=llm,
            messages=[
                {"role": "system", "content": "You are a company profile analyzer."},
                {"role": "user", "content": analysis_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        result = response.choices[0].message.content
        
        # Parse the JSON string into a dictionary
        if isinstance(result, str):
            return json.loads(result)
        return result
        
    except Exception as e:
        print(f"Error extracting company profile: {e}")
        return {"error": str(e)}
    
async def generate_esg_policies(
    deps: CompanyProfileDeps, 
    company_profile: dict,
    esg_parameters: Optional[Dict[str, Any]] = None
) -> str:
    """Generate ESG policies based on company profile, values, and parameters."""
    try:
        # Get additional context about company's current practices
        sustainability_query = "sustainability environmental social governance responsibility"
        additional_context = await retrieve_company_info(deps, sustainability_query)
        
        # Build structured parameter context
        parameter_context = ""
        if esg_parameters:
            parameter_context = "## ESG Policy Parameters from Invest Europe Table 7\n"
            for category, policies in esg_parameters.items():
                parameter_context += f"\n### {category}\n"
                for policy_name, policy_data in policies.items():
                    desc = policy_data['description']
                    parameter_context += f"**{policy_name}**\n"
                    parameter_context += f"- Scope: {desc['Scope'] or 'Not specified'}\n"
                    if desc['Components']:
                        parameter_context += "- Components:\n  * " + "\n  * ".join(
                            [c.strip() for c in str(desc['Components']).split('\n') if c.strip()]
                        ) + "\n"
                    if desc['Targets']:
                        parameter_context += "- Targets:\n  * " + "\n  * ".join(
                            [t.strip() for t in str(desc['Targets']).split('\n') if t.strip()]
                        ) + "\n"
                    if desc['Timeline']:
                        parameter_context += "- Timeline: " + ", ".join(
                            [tl.strip() for tl in str(desc['Timeline']).split('\n') if tl.strip()]
                        ) + "\n"
                    parameter_context += "\n"

        policy_prompt = f"""
        Generate comprehensive ESG policies using these guidelines:

        1. Company Profile Context:
        {company_profile}

        2. Additional Sustainability Context:
        {additional_context}

        3. Required Policy Framework:
        {parameter_context}

        For each ESG category (Environmental, Social, Governance):
        - Start with the relevant policies from the parameters
        - Expand them using company-specific context
        - Include EXACT targets and timelines from parameters where available
        - Add implementation steps that reference the suggested components
        - Align monitoring mechanisms with the specified timelines

        Follow this structure for each policy:
        ### [Policy Name from Parameters]
        **Alignment:** [Connect to company values]
        **Scope:** [From parameters + company context]
        **Targets:** 
        - [Specific targets from parameters]
        - [Additional company-specific targets if needed]
        
        **Implementation:**
        [Steps incorporating components from parameters]
        
        **Timeline:** 
        - Phased implementation based on parameter timelines
        - Key milestones from parameters: [list timelines]
        
        **Monitoring:** 
        - Metrics matching parameter targets
        - Reporting frequency aligned with timeline phases
        """

        response = await deps.openai_client.chat.completions.create(
            model=llm,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": policy_prompt}
            ]
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"Error generating ESG policies: {e}")
        return f"Error in policy generation: {str(e)}"

async def analyze_policy_alignment(
    deps: CompanyProfileDeps,
    company_profile: dict,
    generated_policies: str
) -> str:
    """Analyze alignment between company values and generated ESG policies."""
    try:
        alignment_prompt = f"""
        Analyze the alignment between the company profile and generated ESG policies:

        Company Profile:
        {company_profile}

        Generated Policies:
        {generated_policies}

        Provide analysis of:
        1. Value Alignment - How well do the policies reflect company values?
        2. Feasibility - Are the policies realistic given company context?
        3. Comprehensiveness - Do the policies address all key ESG areas?
        4. Implementation Challenges - What potential obstacles exist?
        5. Recommendations - Suggestions for improving alignment
        
        Format the response in Markdown for better readability.
        """

        response = await deps.openai_client.chat.completions.create(
            model=llm,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": alignment_prompt}
            ]
        )
        
        return response.choices[0].message.content

    except Exception as e:
        print(f"Error analyzing policy alignment: {e}")
        return f"Error in alignment analysis: {str(e)}"