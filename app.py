import streamlit as st
import asyncio
from dotenv import load_dotenv
from litellm import AsyncOpenAI
import os
from crawl import crawl_parallel, get_urls_from_sitemap
from db import init_collection
from excel_utils import process_esg_parameters, validate_esg_parameters, create_parameter_template
import pandas as pd
from io import BytesIO
import json

# Load environment variables
load_dotenv()

# Initialize OpenAI client and ChromaDB collection
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key and not st.secrets.get("OPENAI_API_KEY"):
    st.error("OpenAI API key not found! Please set it in .env file or in Streamlit secrets.")
    
openai_client = AsyncOpenAI(
    api_key=openai_api_key or st.secrets.get("OPENAI_API_KEY")
)

# Initialize ChromaDB collection
collection = init_collection()

# Initialize dependencies for the company profile agent
from company_profile import (
    CompanyProfileDeps,
    retrieve_company_info,
    extract_company_profile,
    generate_esg_policies,
    analyze_policy_alignment
)

# Create dependencies object
deps = CompanyProfileDeps(
    collection=collection,
    openai_client=openai_client
)

# Set up Streamlit page configuration
st.set_page_config(
    page_title="Company Profile & ESG Policy Generator",
    page_icon="🌱",
    layout="wide"
)

def download_template():
    """Create and return template Excel file."""
    df = create_parameter_template()
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Sheet1', index=False)
    return buffer

def main():
    st.title("Company Profile & ESG Policy Generator 🌱")
    
    # Create tabs for different functionalities
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Crawler",
        "ESG Parameters",
        "Company Profile",
        "ESG Policies",
        "Alignment Analysis"
    ])
    
    # Crawler Tab
    with tab1:
        st.header("Crawl Company Website")
        
        input_type = st.radio(
            "Input Type",
            ["Single URL", "Multiple URLs", "Sitemap URL"]
        )
        
        urls_to_crawl = []
        
        if input_type == "Single URL":
            url = st.text_input("Enter company website URL")
            if url:
                urls_to_crawl = [url]
        
        elif input_type == "Multiple URLs":
            urls_text = st.text_area("Enter URLs (one per line)")
            if urls_text:
                urls_to_crawl = [url.strip() for url in urls_text.split("\n") if url.strip()]
        
        else:  # Sitemap URL
            sitemap_url = st.text_input("Enter Sitemap URL")
            if sitemap_url:
                if st.button("Load URLs from Sitemap"):
                    urls_to_crawl = get_urls_from_sitemap(sitemap_url)
                    st.write(f"Found {len(urls_to_crawl)} URLs in sitemap")
        
        if st.button("Start Crawling") and urls_to_crawl:
            st.write(f"Starting to crawl {len(urls_to_crawl)} URLs...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # We need to define this as a non-async function because Streamlit
            # doesn't support top-level await
            def run_crawl():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(crawl_parallel(urls_to_crawl))
                progress_bar.progress(100)
                status_text.write("Crawling completed!")
            
            # Run in a thread to avoid blocking the UI
            import threading
            thread = threading.Thread(target=run_crawl)
            thread.start()
    
    # ESG Parameters Tab
    with tab2:
        st.header("ESG Parameters Configuration")
        
        st.write("""
        Upload an Excel file containing ESG parameters. The file should have a sheet named 'Sheet1' 
        with Invest Europe Table 7 format.
        """)
        
        # Template download
        if st.button("Download Template"):
            buffer = download_template()
            st.download_button(
                label="Download ESG Parameters Template",
                data=buffer.getvalue(),
                file_name="esg_parameters_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        uploaded_file = st.file_uploader("Upload ESG Parameters", type=['xlsx'])
        
        if uploaded_file is not None:
            parameters = process_esg_parameters(uploaded_file)
            
            if parameters and validate_esg_parameters(parameters):
                st.session_state.esg_parameters = parameters
                st.success("ESG parameters successfully loaded!")
                
                # Display parameters in an organized way
                for category, params in parameters.items():
                    with st.expander(f"📋 {category} Parameters"):
                        for param_name, param_data in params.items():
                            st.write(f"**{param_name}**")
                            st.write(f"Value: {param_data['value']}")
                            
                            # Display description fields
                            st.write("Description:")
                            for key, value in param_data['description'].items():
                                if value:
                                    st.write(f"- {key}: {value}")
                            
                            st.write("---")
            else:
                st.error("Invalid parameter file format. Please use the template.")
    
    # Company Profile Tab
    with tab3:
        st.header("Company Profile Analysis")
        
        if st.button("Extract Company Profile"):
            # Check if documents have been crawled
            doc_count = len(collection.get()["ids"]) if collection.get()["ids"] else 0
            
            if doc_count == 0:
                st.warning("No documents in the database. Please crawl company website first.")
            else:
                with st.spinner("Analyzing company information..."):
                    # Define this as a non-async function because Streamlit
                    # doesn't support top-level await
                    def run_extraction():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        profile = loop.run_until_complete(extract_company_profile(deps))
                        return profile
                    
                    profile = run_extraction()
                    
                    # Store in session state
                    st.session_state.company_profile = profile
                    
                    # Display company profile in an organized way
                    if "error" not in profile:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.subheader("Company Overview")
                            st.write(profile.get("Company Overview", "Not available"))
                            
                            st.subheader("Mission")
                            st.write(profile.get("Mission Statement", "Not available"))
                            
                            st.subheader("Vision")
                            st.write(profile.get("Vision Statement", "Not available"))
                        
                        with col2:
                            st.subheader("Core Values")
                            st.write(profile.get("Core Values", "Not available"))
                            
                            st.subheader("Key Objectives")
                            st.write(profile.get("Key Objectives", "Not available"))
                        
                        with st.expander("📚 Sources"):
                            st.write(profile.get("Sources Used", "Not available"))
                    else:
                        st.error(profile["error"])
    
    # ESG Policies Tab
    with tab4:
        st.header("ESG Policy Generation")
        
        if "company_profile" not in st.session_state:
            st.warning("Please extract company profile first.")
        elif "esg_parameters" not in st.session_state:
            st.warning("Please upload ESG parameters first.")
        elif st.button("Generate ESG Policies"):
            with st.spinner("Generating ESG policies..."):
                # Define as a non-async function
                def run_policy_generation():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    policies = loop.run_until_complete(generate_esg_policies(
                        deps, 
                        st.session_state.company_profile,
                        st.session_state.esg_parameters
                    ))
                    return policies
                
                policies = run_policy_generation()
                st.session_state.generated_policies = policies
                st.markdown(policies)
    
    # Alignment Analysis Tab
    with tab5:
        st.header("Policy Alignment Analysis")
        
        if ("company_profile" not in st.session_state or 
            "generated_policies" not in st.session_state):
            st.warning("Please generate company profile and ESG policies first.")
        elif st.button("Analyze Alignment"):
            with st.spinner("Analyzing policy alignment..."):
                # Define as a non-async function
                def run_alignment_analysis():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    alignment = loop.run_until_complete(analyze_policy_alignment(
                        deps,
                        st.session_state.company_profile,
                        st.session_state.generated_policies
                    ))
                    return alignment
                
                alignment = run_alignment_analysis()
                st.markdown(alignment)

    # Sidebar
    with st.sidebar:
        st.header("About")
        st.write("""
        This tool helps you analyze company profiles and generate ESG policies.
        
        Features:
        - Crawl company websites
        - Extract company mission, vision, and objectives
        - Configure custom ESG parameters
        - Generate tailored ESG policies
        - Analyze policy alignment
        """)
        
        st.header("Statistics")
        try:
            doc_count = len(collection.get()["ids"])
            st.metric("Documents in Database", doc_count)
        except Exception as e:
            st.error(f"Error getting document count: {e}")
        
        # Add GitHub link
        st.markdown("---")
        st.markdown(
            "[![GitHub](https://img.shields.io/badge/GitHub-Repository-blue?style=for-the-badge&logo=github)](https://github.com/Miguelramirez004/esg-policy-generator)"
        )

if __name__ == "__main__":
    main()