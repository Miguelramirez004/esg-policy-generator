import streamlit as st
import asyncio
from dotenv import load_dotenv
from litellm import AsyncOpenAI
import os
import pandas as pd
from io import BytesIO
import json
import threading
import nest_asyncio

# Load environment variables
load_dotenv()

# Set up Streamlit page configuration
st.set_page_config(
    page_title="Company Profile & ESG Policy Generator",
    page_icon="🌱",
    layout="wide"
)

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Function to get API key from environment or secrets
def get_openai_api_key():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key and hasattr(st, "secrets") and "OPENAI_API_KEY" in st.secrets:
        api_key = st.secrets["OPENAI_API_KEY"]
    return api_key

# Initialize OpenAI client
def init_openai_client():
    api_key = get_openai_api_key()
    if not api_key:
        st.error("OpenAI API key not found! Please set it in .env file or in Streamlit secrets.")
        return None
    return AsyncOpenAI(api_key=api_key)

# Function to download ESG parameter template
def download_template():
    """Create and return template Excel file."""
    from excel_utils import create_parameter_template
    df = create_parameter_template()
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Sheet1', index=False)
    return buffer

# Function to run an async function in a thread
def run_async_in_thread(async_func, *args, **kwargs):
    """Run an async function in a new thread and return the result."""
    result_container = []
    error_container = []
    
    def run_async():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(async_func(*args, **kwargs))
            result_container.append(result)
        except Exception as e:
            error_container.append(e)
        finally:
            loop.close()
    
    thread = threading.Thread(target=run_async)
    thread.start()
    thread.join()
    
    if error_container:
        raise error_container[0]
    
    return result_container[0] if result_container else None

# Function to get document count safely
def get_document_count(collection):
    """Get the number of documents in the collection, handling different storage backends."""
    try:
        # Check which storage backend we're using (flag set in db.py)
        if st.session_state.get('using_chromadb', False):
            # For ChromaDB
            return len(collection.get()["ids"])
        else:
            # For our simple storage fallback
            return collection.count()
    except Exception as e:
        st.sidebar.warning(f"Error counting documents: {str(e)}")
        return 0

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
    
    # Check for API key
    api_key = get_openai_api_key()
    if not api_key:
        st.sidebar.error("⚠️ OpenAI API key not found! Set it in Streamlit secrets or .env file.")
    
    # Initialize the database collection
    from db import init_collection
    collection = init_collection()
    
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
            if sitemap_url and st.button("Load URLs from Sitemap"):
                # Import here to avoid module-level import issues
                from crawl import get_urls_from_sitemap
                urls_to_crawl = get_urls_from_sitemap(sitemap_url)
                st.write(f"Found {len(urls_to_crawl)} URLs in sitemap")
        
        if st.button("Start Crawling") and urls_to_crawl:
            if not api_key:
                st.error("OpenAI API key is required for crawling")
            else:
                st.write(f"Starting to crawl {len(urls_to_crawl)} URLs...")
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Import crawl function here to avoid module-level import issues
                from crawl import crawl_parallel
                
                # Define a function to run the crawl with a progress bar
                def run_crawl():
                    try:
                        run_async_in_thread(crawl_parallel, urls_to_crawl, api_key)
                        progress_bar.progress(100)
                        status_text.write("Crawling completed!")
                    except Exception as e:
                        status_text.error(f"Error during crawling: {str(e)}")
                
                # Run in a thread to avoid blocking the UI
                thread = threading.Thread(target=run_crawl)
                thread.start()
    
    # ESG Parameters Tab
    with tab2:
        st.header("ESG Parameters Configuration")
        
        st.write("""
        Upload an Excel file containing ESG parameters. The file should include these columns: 
        - Policy (required)
        - Scope
        - Components
        - Targets
        - Timeline
        """)
        
        # Template download
        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("Download Template"):
                buffer = download_template()
                st.download_button(
                    label="Download ESG Parameters Template",
                    data=buffer.getvalue(),
                    file_name="esg_parameters_template.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        
        # Debugging toggle
        with col2:
            show_debug = st.checkbox("Show detailed debugging information")
        
        # File upload section
        uploaded_file = st.file_uploader("Upload ESG Parameters", type=['xlsx', 'xls'])
        
        if uploaded_file is not None:
            # Create an expander for debugging info if checked
            if show_debug:
                with st.expander("Excel Processing Debug Info", expanded=True):
                    st.write("Processing Excel file...")
            
            # Import function here to avoid module-level import issues
            from excel_utils import process_esg_parameters, validate_esg_parameters
            
            # Process with debugging info shown/hidden based on checkbox
            if show_debug:
                parameters = process_esg_parameters(uploaded_file)
            else:
                # Capture and redirect output temporarily
                with st.spinner("Processing Excel file..."):
                    # Create a placeholder for potential errors
                    error_placeholder = st.empty()
                    # Process without showing debug info
                    parameters = process_esg_parameters(uploaded_file)
            
            # Validate parameters
            if parameters and validate_esg_parameters(parameters):
                st.session_state.esg_parameters = parameters
                st.success("ESG parameters successfully loaded!")
                
                # Display parameters in an organized way
                categories_found = []
                for category, params in parameters.items():
                    if params:  # Only show categories with parameters
                        categories_found.append(category)
                        with st.expander(f"📋 {category} Parameters ({len(params)} policies)"):
                            for param_name, param_data in params.items():
                                st.write(f"**{param_name}**")
                                
                                # Display description fields
                                st.write("Details:")
                                for key, value in param_data['description'].items():
                                    if value:
                                        st.write(f"- {key}: {value}")
                                
                                st.write("---")
                
                # Confirm which categories were found
                st.write(f"Found parameters for these categories: {', '.join(categories_found)}")
            else:
                st.error("Invalid parameter file format or missing required categories. The file must contain at least one policy for each ESG category (Environmental, Social, Governance).")
                st.info("Please check your Excel file structure and make sure it has columns for Policy, Scope, Components, Targets, and Timeline. Use the template for guidance.")
    
    # Company Profile Tab
    with tab3:
        st.header("Company Profile Analysis")
        
        if st.button("Extract Company Profile"):
            if not api_key:
                st.error("OpenAI API key is required for profile extraction")
            else:
                # Import CompanyProfileDeps
                from company_profile import CompanyProfileDeps, extract_company_profile
                
                # Initialize dependencies
                openai_client = init_openai_client()
                
                # Check if documents have been crawled
                doc_count = get_document_count(collection)
                
                if doc_count == 0:
                    st.warning("No documents in the database. Please crawl company website first.")
                else:
                    with st.spinner("Analyzing company information..."):
                        deps = CompanyProfileDeps(
                            collection=collection,
                            openai_client=openai_client
                        )
                        
                        try:
                            profile = run_async_in_thread(extract_company_profile, deps)
                            
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
                        except Exception as e:
                            st.error(f"Error extracting company profile: {str(e)}")
    
    # ESG Policies Tab
    with tab4:
        st.header("ESG Policy Generation")
        
        if "company_profile" not in st.session_state:
            st.warning("Please extract company profile first.")
        elif "esg_parameters" not in st.session_state:
            st.warning("Please upload ESG parameters first.")
        elif st.button("Generate ESG Policies"):
            if not api_key:
                st.error("OpenAI API key is required for policy generation")
            else:
                # Import necessary components
                from company_profile import CompanyProfileDeps, generate_esg_policies
                
                with st.spinner("Generating ESG policies..."):
                    # Initialize dependencies again
                    openai_client = init_openai_client()
                    
                    deps = CompanyProfileDeps(
                        collection=collection,
                        openai_client=openai_client
                    )
                    
                    try:
                        policies = run_async_in_thread(
                            generate_esg_policies,
                            deps, 
                            st.session_state.company_profile,
                            st.session_state.esg_parameters
                        )
                        
                        st.session_state.generated_policies = policies
                        st.markdown(policies)
                    except Exception as e:
                        st.error(f"Error generating ESG policies: {str(e)}")
    
    # Alignment Analysis Tab
    with tab5:
        st.header("Policy Alignment Analysis")
        
        if ("company_profile" not in st.session_state or 
            "generated_policies" not in st.session_state):
            st.warning("Please generate company profile and ESG policies first.")
        elif st.button("Analyze Alignment"):
            if not api_key:
                st.error("OpenAI API key is required for alignment analysis")
            else:
                # Import necessary components
                from company_profile import CompanyProfileDeps, analyze_policy_alignment
                
                with st.spinner("Analyzing policy alignment..."):
                    # Initialize dependencies again
                    openai_client = init_openai_client()
                    
                    deps = CompanyProfileDeps(
                        collection=collection,
                        openai_client=openai_client
                    )
                    
                    try:
                        alignment = run_async_in_thread(
                            analyze_policy_alignment,
                            deps,
                            st.session_state.company_profile,
                            st.session_state.generated_policies
                        )
                        
                        st.markdown(alignment)
                    except Exception as e:
                        st.error(f"Error analyzing policy alignment: {str(e)}")

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
            doc_count = get_document_count(collection)
            st.metric("Documents in Database", doc_count)
            
            # Show storage backend info
            if st.session_state.get('using_chromadb', False):
                st.success("Using ChromaDB for document storage")
            else:
                st.info("Using simple document storage (ChromaDB not available)")
        except Exception as e:
            st.error(f"Error getting statistics: {str(e)}")
        
        # Add GitHub link
        st.markdown("---")
        st.markdown(
            "[![GitHub](https://img.shields.io/badge/GitHub-Repository-blue?style=for-the-badge&logo=github)](https://github.com/Miguelramirez004/esg-policy-generator)"
        )
        
        # Add version info
        st.markdown("---")
        st.caption("Version 1.2 - Excel Template Compatibility Fix")

if __name__ == "__main__":
    main()