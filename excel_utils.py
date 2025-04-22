import pandas as pd
from typing import Dict, Any, Optional
import io

def process_esg_parameters(file) -> Optional[Dict[str, Any]]:
    """
    Process Invest Europe Table 7 format Excel file.
    New format columns: Reference | Policy | Possible scope | Possible components | Possible targets | Possible timeline
    """
    try:
        # Read Excel file with correct structure
        df = pd.read_excel(
            file,
            sheet_name='Sheet1',
            skiprows=8,  # Skip metadata rows
            usecols='B:F',  # Use columns B-F (Policy to Possible timeline)
            names=['Policy', 'Scope', 'Components', 'Targets', 'Timeline']
        )

        # Clean up data and remove empty rows
        df = df[df['Policy'].notna()].reset_index(drop=True)

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
            'Cybersecurity & data management policy': 'Governance'
        }

        parameters = {'Environmental': {}, 'Social': {}, 'Governance': {}}
        
        for _, row in df.iterrows():
            policy_name = row['Policy']
            category = category_mapping.get(policy_name, 'Governance')  # Default to Governance
            
            # Build parameter structure
            parameters[category][policy_name] = {
                'value': "N/A",  # Not in original table
                'description': {
                    'Scope': row['Scope'] if not pd.isna(row['Scope']) else None,
                    'Components': row['Components'] if not pd.isna(row['Components']) else None,
                    'Targets': row['Targets'] if not pd.isna(row['Targets']) else None,
                    'Timeline': row['Timeline'] if not pd.isna(row['Timeline']) else None
                }
            }

        return parameters

    except Exception as e:
        print(f"Error processing Excel file: {e}")
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
        'Reference',
        'Policy', 
        'Possible scope', 
        'Possible components', 
        'Possible targets', 
        'Possible timeline'
    ])
    
    # Add example data
    template.loc[0] = [
        "1",
        "Environmental policy", 
        "Company operations, supply chain", 
        "Carbon reduction, waste management", 
        "50% reduction by 2030", 
        "Annual reporting"
    ]
    
    # Return template that will be properly formatted when saved
    return template