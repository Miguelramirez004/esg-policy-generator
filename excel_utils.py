import pandas as pd
from typing import Dict, Any, Optional
import io
import streamlit as st

def process_esg_parameters(file) -> Optional[Dict[str, Any]]:
    """
    Process ESG parameters from uploaded Excel file.
    Flexible parsing to handle different Excel formats.
    """
    try:
        # First try to read without skipping rows to determine the format
        df = pd.read_excel(file)
        
        # Display debugging info
        st.write("Examining Excel file structure...")
        st.write(f"Excel columns: {df.columns.tolist()}")
        st.write(f"First few rows:")
        st.dataframe(df.head(3))
        
        # Try to detect if there's a specific structure
        # If 'Policy' column exists, use that format
        if 'Policy' in df.columns:
            # Already in the right format
            policy_col = 'Policy'
            scope_col = 'Scope' if 'Scope' in df.columns else 'Possible scope'
            components_col = 'Components' if 'Components' in df.columns else 'Possible components'
            targets_col = 'Targets' if 'Targets' in df.columns else 'Possible targets'
            timeline_col = 'Timeline' if 'Timeline' in df.columns else 'Possible timeline'
            
        # If the main format has columns like Reference, Policy, etc.
        elif any(col for col in df.columns if 'Policy' in col):
            # Find the right column names
            policy_col = next((col for col in df.columns if 'Policy' in col), '')
            scope_col = next((col for col in df.columns if 'scope' in col.lower()), '')
            components_col = next((col for col in df.columns if 'component' in col.lower()), '')
            targets_col = next((col for col in df.columns if 'target' in col.lower()), '')
            timeline_col = next((col for col in df.columns if 'time' in col.lower()), '')
            
        else:
            # Try with standard Invest Europe format - skip metadata rows
            df = pd.read_excel(
                file,
                skiprows=8  # Skip metadata rows
            )
            
            # Find column indices by approximate names
            policy_col = next((col for col in df.columns if isinstance(col, str) and 'policy' in col.lower()), None)
            scope_col = next((col for col in df.columns if isinstance(col, str) and 'scope' in col.lower()), None)
            components_col = next((col for col in df.columns if isinstance(col, str) and 'component' in col.lower()), None)
            targets_col = next((col for col in df.columns if isinstance(col, str) and 'target' in col.lower()), None)
            timeline_col = next((col for col in df.columns if isinstance(col, str) and ('time' in col.lower() or 'frame' in col.lower())), None)
        
        # Check if we found the necessary columns
        if not all([policy_col, scope_col, components_col, targets_col, timeline_col]):
            st.error(f"Could not find all required columns. Found: Policy={policy_col}, Scope={scope_col}, Components={components_col}, Targets={targets_col}, Timeline={timeline_col}")
            return None
            
        # Display detected column mapping
        st.success("Found columns for ESG parameters:")
        st.write(f"- Policy column: {policy_col}")
        st.write(f"- Scope column: {scope_col}")
        st.write(f"- Components column: {components_col}")
        st.write(f"- Targets column: {targets_col}")
        st.write(f"- Timeline column: {timeline_col}")

        # Clean up data and remove empty rows
        df = df[df[policy_col].notna()].reset_index(drop=True)

        # Map Invest Europe policies to ESG categories
        category_mapping = {
            'Environmental policy': 'Environmental',
            'Anti-discrimination and equal opportunities policy': 'Social',
            'Diversity & inclusion policy': 'Social',
            '(Occupational) Health & Safety policy': 'Social',
            'Human rights policy': 'Social',
            'Anti-corruption & anti-bribery policy': 'Governance',
            'Privacy of employees & customers policy': 'Governance',
            'Supply chain & responsible procurement policy': 'Governance',
            'Cybersecurity & data management policy': 'Governance',
            # Add more flexible mappings - partial matches
            'Environmental': 'Environmental',
            'Climate': 'Environmental',
            'Sustainability': 'Environmental',
            'Inclusion': 'Social',
            'Diversity': 'Social',
            'Health': 'Social',
            'Safety': 'Social',
            'Human rights': 'Social',
            'Anti-corruption': 'Governance',
            'Privacy': 'Governance',
            'Supply chain': 'Governance',
            'Cybersecurity': 'Governance',
            'Data': 'Governance',
        }

        parameters = {'Environmental': {}, 'Social': {}, 'Governance': {}}
        
        for _, row in df.iterrows():
            policy_name = row[policy_col]
            
            # Skip if policy name is missing
            if pd.isna(policy_name) or not policy_name:
                continue
                
            # Determine category by looking for keywords
            category = None
            for key, value in category_mapping.items():
                if isinstance(policy_name, str) and key.lower() in policy_name.lower():
                    category = value
                    break
                    
            if not category:
                # Default to Governance if no match found
                category = 'Governance'
            
            # Build parameter structure
            parameters[category][policy_name] = {
                'value': "N/A",  # Not in original table
                'description': {
                    'Scope': row.get(scope_col, None) if scope_col in row and not pd.isna(row.get(scope_col)) else None,
                    'Components': row.get(components_col, None) if components_col in row and not pd.isna(row.get(components_col)) else None,
                    'Targets': row.get(targets_col, None) if targets_col in row and not pd.isna(row.get(targets_col)) else None,
                    'Timeline': row.get(timeline_col, None) if timeline_col in row and not pd.isna(row.get(timeline_col)) else None
                }
            }

        return parameters

    except Exception as e:
        st.error(f"Error processing Excel file: {e}")
        return None

def validate_esg_parameters(parameters: Dict[str, Any]) -> bool:
    """Validate we have at least one policy in each ESG category."""
    return all(len(parameters[category]) > 0 for category in ['Environmental', 'Social', 'Governance'])

def create_parameter_template() -> pd.DataFrame:
    """Create template matching Invest Europe Table 7 format."""
    # First create metadata rows for the Excel file
    metadata = pd.DataFrame([
        ["Invest Europe ESG Parameters Template"],
        ["Based on Table 7 - Policies"],
        [""],
        ["Instructions:"],
        ["1. Fill in the policy details below"],
        ["2. Do not modify column names or structure"],
        ["3. Upload this file to the ESG Policy Generator"],
        [""]
    ])
    
    # Then create the actual template
    template = pd.DataFrame(columns=[
        'Policy', 
        'Scope', 
        'Components', 
        'Targets', 
        'Timeline'
    ])
    
    # Add example data
    template.loc[0] = [
        "Environmental policy", 
        "Company operations, supply chain", 
        "Carbon reduction, waste management", 
        "50% reduction by 2030", 
        "Annual reporting"
    ]
    
    template.loc[1] = [
        "Diversity & inclusion policy", 
        "All employees and hiring processes", 
        "Training programs, reporting mechanisms", 
        "Gender parity in leadership", 
        "Quarterly reviews"
    ]
    
    template.loc[2] = [
        "Anti-corruption & anti-bribery policy", 
        "All business operations", 
        "Due diligence, whistleblower protection", 
        "Zero tolerance for violations", 
        "Annual training"
    ]
    
    # Return template that will be properly formatted when saved
    return template