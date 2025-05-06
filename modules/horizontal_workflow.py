import streamlit as st
import logging

logger = logging.getLogger(__name__)

# Define the workflow steps (centralized definition)
workflow_steps = [
    {
        "id": "authentication",
        "title": "Login",
        "page": "Home",
        "icon": "🔑" # Icon might be hard to fit nicely in chevrons
    },
    {
        "id": "file_browser",
        "title": "Select Files",
        "page": "File Browser",
        "icon": "📁"
    },
    {
        "id": "document_categorization",
        "title": "Categorize",
        "page": "Document Categorization",
        "icon": "🏷️"
    },
    {
        "id": "metadata_config",
        "title": "Configure",
        "page": "Metadata Configuration",
        "icon": "⚙️"
    },
    {
        "id": "process_files",
        "title": "Process",
        "page": "Process Files",
        "icon": "🔄"
    },
    {
        "id": "view_results",
        "title": "Review",
        "page": "View Results",
        "icon": "👁️"
    },
    {
        "id": "apply_metadata",
        "title": "Apply",
        "page": "Apply Metadata",
        "icon": "✅"
    }
]

# Removed navigate_to_step function as navigation is handled by sidebar now
# def navigate_to_step(page_id):
#     ...

def display_horizontal_workflow(current_page_id: str):
    """
    Displays the horizontal workflow indicator using Salesforce-style chevrons.
    This version is purely visual and does not handle clicks.

    Args:
        current_page_id: The page ID of the current step (e.g., "Home", "File Browser").
    """
    
    # Find the index of the current step
    current_step_index = -1
    for i, step in enumerate(workflow_steps):
        if step["page"] == current_page_id:
            current_step_index = i
            break
            
    # Inject CSS for chevron styling
    css = """
    <style>
        .chevron-container {
            display: flex;
            justify-content: center; /* Center the chevrons */
            list-style: none;
            padding: 0;
            margin: 20px 0; /* Add some margin */
            width: 100%;
            overflow-x: auto; /* Allow horizontal scrolling if needed */
        }
        .chevron-step {
            background-color: #e9ecef; /* Default upcoming background */
            color: #6c757d; /* Default upcoming text */
            padding: 0.5rem 1rem 0.5rem 2rem; /* Adjust padding */
            margin-right: -1rem; /* Overlap chevrons */
            position: relative;
            text-align: center;
            min-width: 120px; /* Minimum width for each step */
            white-space: nowrap;
            border: 1px solid #ced4da;
            cursor: default; /* Default cursor - not clickable */
        }
        .chevron-step::before, .chevron-step::after {
            content: "";
            position: absolute;
            top: 0;
            border: 0 solid transparent;
            border-width: 1.55rem 1rem; /* Controls size/angle of arrow */
            width: 0;
            height: 0;
        }
        .chevron-step::before {
            left: -0.05rem; /* Position left arrow */
            border-left-color: white; /* Match page background */
            border-left-width: 1rem;
        }
        .chevron-step::after {
            left: 100%;
            z-index: 2;
            border-left-color: #e9ecef; /* Match step background */
        }
        /* First step doesn't need the left cutout */
        .chevron-step:first-child {
            padding-left: 1rem;
            border-top-left-radius: 5px;
            border-bottom-left-radius: 5px;
        }
        .chevron-step:first-child::before {
            display: none;
        }
        /* Last step doesn't need the right arrow */
        .chevron-step:last-child {
            margin-right: 0;
            padding-right: 1rem;
            border-top-right-radius: 5px;
            border-bottom-right-radius: 5px;
        }
        .chevron-step:last-child::after {
            display: none;
        }

        /* Completed Step Styling */
        .chevron-step-completed {
            background-color: #cfe2ff; /* Light blue background */
            color: #052c65; /* Dark blue text */
            border-color: #9ec5fe;
            /* cursor: pointer; Removed - not clickable */
        }
        .chevron-step-completed::after {
            border-left-color: #cfe2ff; /* Match completed background */
        }
        /* Removed hover styles as it's not interactive */
        /* .chevron-step-completed:hover { ... } */
        /* .chevron-step-completed:hover::after { ... } */

        /* Current Step Styling */
        .chevron-step-current {
            background-color: #0d6efd; /* Blue background */
            color: white;
            font-weight: bold;
            z-index: 3; /* Ensure current step overlaps others */
            border-color: #0a58ca;
        }
        .chevron-step-current::after {
            border-left-color: #0d6efd; /* Match current background */
        }
        
        /* Removed link styling as it's not interactive */
        /* .chevron-step a { ... } */

    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

    # Generate HTML for the chevrons
    html_content = "<div class=\"chevron-container\">"
    
    for i, step in enumerate(workflow_steps):
        # Determine CSS class based on status
        status_class = ""
        if i < current_step_index:
            status_class = "chevron-step-completed"
        elif i == current_step_index:
            status_class = "chevron-step-current"
        else:
            status_class = "chevron-step-upcoming" # Default class defined above

        step_html = f"<div class=\"chevron-step {status_class}\" "
        step_html += f" title=\"{step['title']} (Step {i+1})\">" # Add step number to title
        
        # Display title
        step_html += f"{step['title']}"
        # Add checkmark for completed steps
        if i < current_step_index:
             step_html += " ✓"
             
        step_html += "</div>"
        html_content += step_html
        
    html_content += "</div>"
    
    # Render the visual chevrons
    st.markdown(html_content, unsafe_allow_html=True)

    # --- REMOVED Click Handling Section --- 
    # The st.columns and st.button logic previously here has been removed.
    # Navigation is now handled by the sidebar buttons in app.py.


