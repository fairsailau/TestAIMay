import streamlit as st
import logging
import json
import requests
import re
import os
import datetime
import pandas as pd
import altair as alt
from typing import Dict, Any, List, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def document_categorization():
    """
    Enhanced document categorization with improved confidence metrics
    """
    st.title("Document Categorization")
    
    if not st.session_state.authenticated or not st.session_state.client:
        st.error("Please authenticate with Box first")
        return
    
    if not st.session_state.selected_files:
        st.warning("No files selected. Please select files in the File Browser first.")
        if st.button("Go to File Browser", key="go_to_file_browser_button_cat"):
            st.session_state.current_page = "File Browser"
            st.rerun()
        return
    
    # Initialize document categorization state if not exists
    if "document_categorization" not in st.session_state:
        st.session_state.document_categorization = {
            "is_categorized": False,
            "results": {},
            "errors": {}
        }
    
    # Initialize confidence thresholds if not exists
    if "confidence_thresholds" not in st.session_state:
        st.session_state.confidence_thresholds = {
            "auto_accept": 0.85,
            "verification": 0.6,
            "rejection": 0.4
        }
    
    # Initialize document types if not exists (NEW STRUCTURE: List of Dicts)
    if "document_types" not in st.session_state:
        st.session_state.document_types = [
            {"name": "Sales Contract", "description": "Contracts related to sales agreements and terms."},
            {"name": "Invoices", "description": "Billing documents issued by a seller to a buyer, indicating quantities, prices for products or services."},
            {"name": "Tax", "description": "Documents related to government taxation (e.g., tax forms, filings, receipts)."},
            {"name": "Financial Report", "description": "Reports detailing the financial status or performance of an entity (e.g., balance sheets, income statements)."},
            {"name": "Employment Contract", "description": "Agreements outlining terms and conditions of employment between an employer and employee."},
            {"name": "PII", "description": "Documents containing Personally Identifiable Information that needs careful handling."},
            {"name": "Other", "description": "Any document not fitting into the specific categories above."}
        ]
    
    # Display selected files
    num_files = len(st.session_state.selected_files)
    st.write(f"Ready to categorize {num_files} files using Box AI.")
    
    # Create tabs for main interface and settings
    tab1, tab2 = st.tabs(["Categorization", "Settings"])
    
    with tab1:
        # AI Model selection
        ai_models = [
            "azure__openai__gpt_4o_mini",
            "azure__openai__gpt_4o_2024_05_13",
            "google__gemini_2_0_flash_001",
            "google__gemini_2_0_flash_lite_preview",
            "google__gemini_1_5_flash_001",
            "google__gemini_1_5_pro_001",
            "aws__claude_3_haiku",
            "aws__claude_3_sonnet",
            "aws__claude_3_5_sonnet",
            "aws__claude_3_7_sonnet",
            "aws__titan_text_lite"
        ]
        
        selected_model = st.selectbox(
            "Select AI Model for Categorization",
            options=ai_models,
            index=0,
            key="ai_model_select_cat",
            help="Choose the AI model to use for document categorization"
        )
        
        # Enhanced categorization options
        st.write("### Categorization Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Two-stage categorization option
            use_two_stage = st.checkbox(
                "Use two-stage categorization",
                value=True,
                help="When enabled, documents with low confidence will undergo a second analysis"
            )
            
            # Multi-model consensus option
            use_consensus = st.checkbox(
                "Use multi-model consensus",
                value=False,
                help="When enabled, multiple AI models will be used and their results combined for more accurate categorization"
            )
        
        with col2:
            # Confidence threshold for second-stage
            confidence_threshold = st.slider(
                "Confidence threshold for second-stage",
                min_value=0.0,
                max_value=1.0,
                value=0.6,
                step=0.05,
                help="Documents with confidence below this threshold will undergo second-stage analysis",
                disabled=not use_two_stage
            )
            
            # Select models for consensus
            consensus_models = []
            if use_consensus:
                consensus_models = st.multiselect(
                    "Select models for consensus",
                    options=ai_models,
                    default=[ai_models[0], ai_models[2]] if len(ai_models) > 2 else ai_models[:1],
                    help="Select 2-3 models for best results (more models will increase processing time)"
                )
                
                if len(consensus_models) < 1:
                    st.warning("Please select at least one model for consensus categorization")
        
        # Categorization controls
        col1, col2 = st.columns(2)
        
        with col1:
            start_button = st.button("Start Categorization", key="start_categorization_button_cat", use_container_width=True)
        
        with col2:
            cancel_button = st.button("Cancel Categorization", key="cancel_categorization_button_cat", use_container_width=True)
        
        # Process categorization
        if start_button:
            with st.spinner("Categorizing documents..."):
                # Reset categorization results
                st.session_state.document_categorization = {
                    "is_categorized": False,
                    "results": {},
                    "errors": {}
                }
                
                # Process each file
                for file in st.session_state.selected_files:
                    file_id = file["id"]
                    file_name = file["name"]
                    
                    try:
                        if use_consensus and consensus_models:
                            # Multi-model consensus categorization
                            consensus_results = []
                            
                            # Create progress bar for models
                            model_progress = st.progress(0)
                            model_status = st.empty()
                            
                            # Process with each model
                            for i, model in enumerate(consensus_models):
                                model_status.text(f"Processing with {model}...")
                                result = categorize_document(file_id, model)
                                consensus_results.append(result)
                                model_progress.progress((i + 1) / len(consensus_models))
                            
                            # Clear progress indicators
                            model_progress.empty()
                            model_status.empty()
                            
                            # Combine results using weighted voting
                            result = combine_categorization_results(consensus_results)
                            
                            # Add model details to reasoning
                            models_text = ", ".join(consensus_models)
                            result["reasoning"] = f"Consensus from models: {models_text}\n\n" + result["reasoning"]
                        else:
                            # First-stage categorization
                            result = categorize_document(file_id, selected_model)
                            
                            # Check if second-stage is needed
                            if use_two_stage and result["confidence"] < confidence_threshold:
                                st.info(f"Low confidence ({result['confidence']:.2f}) for {file_name}, performing detailed analysis...")
                                # Second-stage categorization with more detailed prompt
                                detailed_result = categorize_document_detailed(file_id, selected_model, result["document_type"])
                                
                                # Merge results, preferring the detailed analysis
                                result = {
                                    "document_type": detailed_result["document_type"],
                                    "confidence": detailed_result["confidence"],
                                    "reasoning": detailed_result["reasoning"],
                                    "first_stage_type": result["document_type"],
                                    "first_stage_confidence": result["confidence"]
                                }
                        
                        # Extract document features for multi-factor confidence
                        document_features = extract_document_features(file_id)
                        
                        # Calculate multi-factor confidence
                        # Extract names for calculation function
                        document_type_names = [dtype["name"] for dtype in st.session_state.document_types]
                        
                        multi_factor_confidence = calculate_multi_factor_confidence(
                            result["confidence"],
                            document_features,
                            result["document_type"],
                            result.get("reasoning", ""),
                            document_type_names # Pass only names here
                        )
                        
                        # Apply confidence calibration if available
                        calibrated_confidence = apply_confidence_calibration(
                            result["document_type"],
                            multi_factor_confidence["overall"]
                        )
                        
                        # Store result with enhanced confidence data
                        st.session_state.document_categorization["results"][file_id] = {
                            "file_id": file_id,
                            "file_name": file_name,
                            "document_type": result["document_type"],
                            "confidence": result["confidence"],  # Original AI confidence
                            "multi_factor_confidence": multi_factor_confidence,  # Detailed confidence factors
                            "calibrated_confidence": calibrated_confidence,  # Calibrated overall confidence
                            "reasoning": result["reasoning"],
                            "first_stage_type": result.get("first_stage_type"),
                            "first_stage_confidence": result.get("first_stage_confidence"),
                            "document_features": document_features
                        }
                    except Exception as e:
                        logger.error(f"Error categorizing document {file_name}: {str(e)}")
                        st.session_state.document_categorization["errors"][file_id] = {
                            "file_id": file_id,
                            "file_name": file_name,
                            "error": str(e)
                        }
                
                # Apply confidence thresholds
                st.session_state.document_categorization["results"] = apply_confidence_thresholds(
                    st.session_state.document_categorization["results"]
                )
                
                # Mark as categorized
                st.session_state.document_categorization["is_categorized"] = True
                
                # Show success message
                num_processed = len(st.session_state.document_categorization["results"])
                num_errors = len(st.session_state.document_categorization["errors"])
                
                if num_errors == 0:
                    st.success(f"Categorization complete! Processed {num_processed} files.")
                else:
                    st.warning(f"Categorization complete! Processed {num_processed} files with {num_errors} errors.")
        
        # Display categorization results
        if st.session_state.document_categorization.get("is_categorized", False):
            display_categorization_results()
    
    with tab2:
        # Confidence settings
        st.write("### Confidence Configuration")
        
        # Confidence threshold configuration
        configure_confidence_thresholds()
        
        # Document Types Configuration
        st.write("### Document Types Configuration")
        configure_document_types()
        
        # Confidence validation
        with st.expander("Confidence Validation", expanded=False):
            validate_confidence_with_examples()

def configure_document_types():
    """
    Configure user-defined document types with descriptions.
    """
    st.write("Define custom document types and their descriptions for categorization:")
    
    # Ensure document_types exists and is a list of dicts
    if "document_types" not in st.session_state or not isinstance(st.session_state.document_types, list):
        # Initialize or reset to default structure if invalid
        st.session_state.document_types = [
            {"name": "Sales Contract", "description": "Contracts related to sales agreements and terms."},
            {"name": "Invoices", "description": "Billing documents issued by a seller to a buyer, indicating quantities, prices for products or services."},
            {"name": "Tax", "description": "Documents related to government taxation (e.g., tax forms, filings, receipts)."},
            {"name": "Financial Report", "description": "Reports detailing the financial status or performance of an entity (e.g., balance sheets, income statements)."},
            {"name": "Employment Contract", "description": "Agreements outlining terms and conditions of employment between an employer and employee."},
            {"name": "PII", "description": "Documents containing Personally Identifiable Information that needs careful handling."},
            {"name": "Other", "description": "Any document not fitting into the specific categories above."}
        ]
        logger.warning("Document types state was missing or invalid, reset to default structure.")

    # Display current document types with descriptions and delete buttons
    indices_to_delete = []
    for i, doc_type_dict in enumerate(st.session_state.document_types):
        is_other_type = doc_type_dict.get("name") == "Other"
        
        with st.container():
            st.markdown(f"**Document Type {i+1}**")
            col1, col2 = st.columns([3, 1])
            with col1:
                # Input for Name
                current_name = doc_type_dict.get("name", "")
                new_name = st.text_input(
                    f"Name", 
                    value=current_name, 
                    key=f"doc_type_name_{i}", 
                    disabled=is_other_type, 
                    help="The name of the document category."
                )
                if new_name != current_name and not is_other_type:
                    # Check for duplicate names before updating
                    if any(d["name"] == new_name for j, d in enumerate(st.session_state.document_types) if i != j):
                        st.warning(f"Document type name '{new_name}' already exists.")
                    else:
                        st.session_state.document_types[i]["name"] = new_name
                        logger.info(f"Updated document type name at index {i} to: {new_name}")
                        # No rerun here, allow multiple edits before rerun

                # Input for Description
                current_desc = doc_type_dict.get("description", "")
                new_desc = st.text_area(
                    f"Description", 
                    value=current_desc, 
                    key=f"doc_type_desc_{i}", 
                    disabled=is_other_type, 
                    height=100,
                    help="Provide a clear description for the AI to understand this category."
                )
                if new_desc != current_desc and not is_other_type:
                    st.session_state.document_types[i]["description"] = new_desc
                    logger.info(f"Updated document type description at index {i}")
                    # No rerun here

            with col2:
                # Delete button (disabled for "Other")
                st.write("&nbsp;") # Add space for alignment
                if st.button("Delete", key=f"delete_type_{i}", disabled=is_other_type):
                    indices_to_delete.append(i)
                    logger.info(f"Marked document type at index {i} for deletion.")
            st.markdown("---")

    # Process deletions if any button was pressed
    if indices_to_delete:
        # Sort indices in reverse order to avoid index shifting issues during deletion
        indices_to_delete.sort(reverse=True)
        for index in indices_to_delete:
            deleted_type = st.session_state.document_types.pop(index)
            logger.info(f"Deleted document type: {deleted_type.get('name')}")
        st.rerun() # Rerun after deletion to update the UI

    # Add new document type section
    st.write("**Add New Document Type**")
    new_type_name = st.text_input("New Type Name", key="new_doc_type_name")
    new_type_desc = st.text_area("New Type Description", key="new_doc_type_desc", height=100)
    
    if st.button("Add Document Type") and new_type_name:
        # Check if name already exists
        if any(d['name'] == new_type_name for d in st.session_state.document_types):
            st.warning(f"Document type name '{new_type_name}' already exists.")
        else:
            new_doc_type = {"name": new_type_name, "description": new_type_desc}
            st.session_state.document_types.append(new_doc_type)
            logger.info(f"Added new document type: {new_doc_type}")
            st.rerun() # Rerun to display the newly added type
    
    # Reset to defaults button
    if st.button("Reset to Defaults"):
        st.session_state.document_types = [
            {"name": "Sales Contract", "description": "Contracts related to sales agreements and terms."},
            {"name": "Invoices", "description": "Billing documents issued by a seller to a buyer, indicating quantities, prices for products or services."},
            {"name": "Tax", "description": "Documents related to government taxation (e.g., tax forms, filings, receipts)."},
            {"name": "Financial Report", "description": "Reports detailing the financial status or performance of an entity (e.g., balance sheets, income statements)."},
            {"name": "Employment Contract", "description": "Agreements outlining terms and conditions of employment between an employer and employee."},
            {"name": "PII", "description": "Documents containing Personally Identifiable Information that needs careful handling."},
            {"name": "Other", "description": "Any document not fitting into the specific categories above."}
        ]
        logger.info("Reset document types to default values.")
        st.rerun()

def display_categorization_results():
    """
    Display categorization results with enhanced confidence visualization
    """
    st.write("### Categorization Results")
    
    # Get results from session state
    results = st.session_state.document_categorization.get("results", {})
    
    if not results:
        st.info("No categorization results available.")
        return
    
    # Extract category names for UI elements
    document_type_names = [dtype['name'] for dtype in st.session_state.document_types]
    
    # Create tabs for different views
    tab1, tab2 = st.tabs(["Table View", "Detailed View"])
    
    with tab1:
        # Create a table of results with enhanced confidence display
        results_data = []
        for file_id, result in results.items():
            # Determine status based on thresholds
            status = result.get("status", "Review")
            
            # Determine confidence level and color
            confidence = result.get("calibrated_confidence", result.get("confidence", 0.0))
            if confidence >= 0.8:
                confidence_level = "High"
                confidence_color = "green"
            elif confidence >= 0.6:
                confidence_level = "Medium"
                confidence_color = "orange"
            else:
                confidence_level = "Low"
                confidence_color = "red"
            
            results_data.append({
                "File Name": result.get("file_name", "Unknown"),
                "Document Type": result.get("document_type", "N/A"),
                "Confidence": f"<span style='color: {confidence_color};'>{confidence_level} ({confidence:.2f})</span>",
                "Status": status
            })
        
        if results_data:
            # Convert to DataFrame for display
            df = pd.DataFrame(results_data)
            
            # Display as HTML to preserve formatting
            st.markdown(
                df.to_html(escape=False, index=False),
                unsafe_allow_html=True
            )
        else:
            st.info("No results to display in table view.")
    
    with tab2:
        # Create detailed view with confidence visualization
        if not results:
             st.info("No results to display in detailed view.")
             return
             
        for file_id, result in results.items():
            with st.container(border=True):
                st.write(f"### {result.get('file_name', 'Unknown')}")
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    # Display document type and confidence
                    current_doc_type = result.get("document_type", "N/A")
                    st.write(f"**Category:** {current_doc_type}")
                    
                    # Display confidence visualization
                    if "multi_factor_confidence" in result:
                        display_confidence_visualization(result["multi_factor_confidence"])
                    else:
                        # Fallback for results without multi-factor confidence
                        confidence = result.get("confidence", 0.0)
                        if confidence >= 0.8:
                            confidence_color = "#28a745"  # Green
                        elif confidence >= 0.6:
                            confidence_color = "#ffc107"  # Yellow
                        else:
                            confidence_color = "#dc3545"  # Red
                        
                        st.markdown(
                            f"""
                            <div style="margin-bottom: 10px;">
                                <div style="display: flex; align-items: center; margin-bottom: 5px;">
                                    <div style="font-weight: bold; margin-right: 10px;">Confidence:</div>
                                    <div style="font-weight: bold; color: {confidence_color};">{confidence:.2f}</div>
                                </div>
                                <div style="width: 100%; background-color: #f0f0f0; height: 10px; border-radius: 5px; overflow: hidden;">
                                    <div style="width: {confidence*100}%; background-color: {confidence_color}; height: 100%;"></div>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    
                    # Display confidence explanation
                    if "multi_factor_confidence" in result:
                        explanations = get_confidence_explanation(
                            result["multi_factor_confidence"],
                            current_doc_type
                        )
                        st.info(explanations["overall"])
                    
                    # Display reasoning
                    with st.expander("Reasoning", expanded=False):
                        st.write(result.get("reasoning", "No reasoning provided"))
                    
                    # Display first-stage results if available
                    if result.get("first_stage_type"):
                        with st.expander("First-Stage Results", expanded=False):
                            st.write(f"**First-stage category:** {result['first_stage_type']}")
                            st.write(f"**First-stage confidence:** {result['first_stage_confidence']:.2f}")
                
                with col2:
                    # Category override
                    st.write("**Override Category:**")
                    try:
                        current_index = document_type_names.index(current_doc_type) if current_doc_type in document_type_names else 0
                    except ValueError:
                        current_index = 0 # Default to first item if current type not found
                        
                    new_category = st.selectbox(
                        "Select category",
                        options=document_type_names, # Use only names for options
                        index=current_index,
                        key=f"override_{file_id}"
                    )
                    
                    if st.button("Apply Override", key=f"apply_override_{file_id}"):
                        # Save feedback for calibration
                        save_categorization_feedback(file_id, current_doc_type, new_category)
                        
                        # Update the result
                        st.session_state.document_categorization["results"][file_id]["document_type"] = new_category
                        st.session_state.document_categorization["results"][file_id]["confidence"] = 1.0
                        st.session_state.document_categorization["results"][file_id]["calibrated_confidence"] = 1.0
                        st.session_state.document_categorization["results"][file_id]["reasoning"] += "\n\nManually overridden by user."
                        st.session_state.document_categorization["results"][file_id]["status"] = "Accepted"
                        
                        logger.info(f"User override applied for file {file_id}. New category: {new_category}")
                        st.success(f"Category updated to {new_category}")
                        st.rerun()
                    
                    # Document preview (Optional - Placeholder)
                    # st.write("**Document Preview:**")
                    # preview_url = get_document_preview_url(file_id)
                    # if preview_url:
                    #     st.image(preview_url, caption="Document Preview", use_column_width=True)
                    # else:
                    #     st.info("Preview not available.")
                
                # User feedback section (Optional - Placeholder)
                # with st.expander("Provide Feedback", expanded=False):
                #     collect_user_feedback(file_id, result)
                
                # st.markdown("---") # Separator removed, using container border
        
        # Continue button
        st.write("---")
        if st.button("Continue to Metadata Configuration", key="continue_to_metadata_button_cat", use_container_width=True):
            st.session_state.current_page = "Metadata Configuration"
            st.rerun()

def categorize_document(file_id: str, model: str = "azure__openai__gpt_4o_mini") -> Dict[str, Any]:
    """
    Categorize a document using Box AI
    
    Args:
        file_id: Box file ID
        model: AI model to use for categorization
        
    Returns:
        dict: Document categorization result
    """
    # Get access token from client
    access_token = None
    if hasattr(st.session_state.client, '_oauth'):
        access_token = st.session_state.client._oauth.access_token
    elif hasattr(st.session_state.client, 'auth') and hasattr(st.session_state.client.auth, 'access_token'):
        access_token = st.session_state.client.auth.access_token
    
    if not access_token:
        raise ValueError("Could not retrieve access token from client")
    
    # Set headers
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    # Get document types (list of dicts) from session state
    document_types_with_desc = st.session_state.document_types
    document_type_names = [dtype['name'] for dtype in document_types_with_desc]
    
    # Create prompt for document categorization with confidence score request
    # Include descriptions in the prompt
    category_options_text = "\n".join([f"- {dtype['name']}: {dtype['description']}" for dtype in document_types_with_desc])
    
    prompt = (
        f"Analyze this document and determine which category it belongs to from the following options:\n"
        f"{category_options_text}\n\n"
        f"Provide your answer ONLY in the following format (exactly two lines):\n"
        f"Category: [selected category name]\n"
        f"Confidence: [confidence score between 0 and 1, where 1 is highest confidence]\n"
        f"Reasoning: [detailed explanation of your categorization, including key features of the document that support this categorization]"
    )
    
    # Construct API URL for Box AI Ask
    api_url = "https://api.box.com/2.0/ai/ask"
    
    # Construct request body according to the API documentation
    request_body = {
        "mode": "single_item_qa",  # Required parameter - single_item_qa or multiple_item_qa
        "prompt": prompt,
        "items": [
            {
                "type": "file",
                "id": file_id
            }
        ],
        "ai_agent": {
            "type": "ai_agent_ask",
            "basic_text": {
                "model": model,
                "mode": "default"  # Required parameter for basic_text
            }
        }
    }
    
    try:
        # Make API call
        logger.info(f"Making Box AI API call with request: {json.dumps(request_body)}")
        response = requests.post(api_url, headers=headers, json=request_body)
        
        # Log response for debugging
        logger.info(f"Box AI API response status: {response.status_code}")
        if response.status_code != 200:
            logger.error(f"Box AI API error response: {response.text}")
            # Try to parse error details from Box response
            error_details = "Unknown error"
            try:
                error_json = response.json()
                error_details = error_json.get('message', response.text)
            except json.JSONDecodeError:
                error_details = response.text
            raise Exception(f"Error in Box AI API call: {response.status_code}. Details: {error_details}")
        
        # Parse response
        response_data = response.json()
        logger.info(f"Box AI API response data: {json.dumps(response_data)}")
        
        # Extract answer from response
        if "answer" in response_data:
            answer_text = response_data["answer"]
            
            # Parse the structured response to extract category, confidence, and reasoning
            document_type, confidence, reasoning = parse_categorization_response(answer_text, document_type_names)
            
            return {
                "document_type": document_type,
                "confidence": confidence,
                "reasoning": reasoning
            }
        
        # If no answer in response, return default
        logger.warning(f"No 'answer' field found in Box AI response for file {file_id}. Response: {response_data}")
        return {
            "document_type": "Other",
            "confidence": 0.0,
            "reasoning": "Could not determine document type (No answer from AI)"
        }
    
    except Exception as e:
        logger.exception(f"Error during Box AI API call or parsing for file {file_id}: {str(e)}")
        raise Exception(f"Error categorizing document {file_id}: {str(e)}")

def categorize_document_detailed(file_id: str, model: str, initial_category: str) -> Dict[str, Any]:
    """
    Perform a more detailed categorization for documents with low confidence
    
    Args:
        file_id: Box file ID
        model: AI model to use for categorization
        initial_category: Initial category from first-stage categorization
        
    Returns:
        dict: Document categorization result
    """
    # Get access token from client
    access_token = None
    if hasattr(st.session_state.client, '_oauth'):
        access_token = st.session_state.client._oauth.access_token
    elif hasattr(st.session_state.client, 'auth') and hasattr(st.session_state.client.auth, 'access_token'):
        access_token = st.session_state.client.auth.access_token
    
    if not access_token:
        raise ValueError("Could not retrieve access token from client")
    
    # Set headers
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    # Get document types (list of dicts) from session state
    document_types_with_desc = st.session_state.document_types
    document_type_names = [dtype['name'] for dtype in document_types_with_desc]
    
    # Create a more detailed prompt for second-stage analysis, including descriptions
    category_options_text = "\n".join([f"- {dtype['name']}: {dtype['description']}" for dtype in document_types_with_desc])

    prompt = (
        f"Analyze this document in detail to determine its category. "
        f"The initial categorization suggested it might be '{initial_category}', but we need a more thorough analysis.\n\n"
        f"Consider the following categories and their descriptions:\n"
        f"{category_options_text}\n\n"
        f"For each category listed above, provide a score from 0-10 indicating how well the document matches that category, "
        f"along with specific evidence from the document supporting your score.\n\n"
        f"Finally, provide your definitive categorization ONLY in the following format (exactly two lines):\n"
        f"Category: [selected category name]\n"
        f"Confidence: [confidence score between 0 and 1, where 1 is highest confidence]\n"
        f"Reasoning: [detailed explanation with specific evidence from the document supporting your final choice]"
    )
    
    # Construct API URL for Box AI Ask
    api_url = "https://api.box.com/2.0/ai/ask"
    
    # Construct request body according to the API documentation
    request_body = {
        "mode": "single_item_qa",
        "prompt": prompt,
        "items": [
            {
                "type": "file",
                "id": file_id
            }
        ],
        "ai_agent": {
            "type": "ai_agent_ask",
            "basic_text": {
                "model": model,
                "mode": "default"
            }
        }
    }
    
    try:
        # Make API call
        logger.info(f"Making detailed Box AI API call with request: {json.dumps(request_body)}")
        response = requests.post(api_url, headers=headers, json=request_body)
        
        # Check response
        if response.status_code != 200:
            logger.error(f"Box AI API error response: {response.text}")
            # Try to parse error details
            error_details = "Unknown error"
            try:
                error_json = response.json()
                error_details = error_json.get('message', response.text)
            except json.JSONDecodeError:
                error_details = response.text
            raise Exception(f"Error in detailed Box AI API call: {response.status_code}. Details: {error_details}")
        
        # Parse response
        response_data = response.json()
        logger.info(f"Detailed Box AI API response data: {json.dumps(response_data)}")
        
        # Extract answer from response
        if "answer" in response_data:
            answer_text = response_data["answer"]
            
            # Parse the structured response
            document_type, confidence, reasoning = parse_categorization_response(answer_text, document_type_names)
            
            return {
                "document_type": document_type,
                "confidence": confidence,
                "reasoning": reasoning
            }
        
        # If no answer, return default
        logger.warning(f"No 'answer' field found in detailed Box AI response for file {file_id}. Response: {response_data}")
        return {
            "document_type": initial_category, # Fallback to initial category
            "confidence": 0.0,
            "reasoning": "Could not determine document type in detailed analysis (No answer from AI)"
        }
    
    except Exception as e:
        logger.exception(f"Error during detailed Box AI API call or parsing for file {file_id}: {str(e)}")
        raise Exception(f"Error in detailed categorization for document {file_id}: {str(e)}")

def parse_categorization_response(response_text: str, valid_categories: List[str]) -> Tuple[str, float, str]:
    """
    Parse the structured response from the AI to extract category, confidence, and reasoning.
    Handles potential variations in the AI response format.

    Args:
        response_text (str): The text response from the AI.
        valid_categories (List[str]): A list of valid category names.

    Returns:
        Tuple[str, float, str]: Extracted document type, confidence score, and reasoning.
                                Returns ("Other", 0.0, "Parsing failed") if parsing is unsuccessful.
    """
    document_type = "Other" # Default category
    confidence = 0.0       # Default confidence
    reasoning = ""         # Default reasoning

    try:
        # Use regex to find Category, Confidence, and Reasoning, allowing for variations
        category_match = re.search(r"^Category:\s*(.*?)$", response_text, re.MULTILINE | re.IGNORECASE)
        confidence_match = re.search(r"^Confidence:\s*([0-9.]+)", response_text, re.MULTILINE | re.IGNORECASE)
        reasoning_match = re.search(r"^Reasoning:\s*(.*)", response_text, re.MULTILINE | re.IGNORECASE | re.DOTALL)

        if category_match:
            extracted_category = category_match.group(1).strip()
            # Validate against known categories
            if extracted_category in valid_categories:
                document_type = extracted_category
            else:
                logger.warning(f"Extracted category '{extracted_category}' not in valid list: {valid_categories}. Defaulting to 'Other'.")
        else:
            logger.warning(f"Could not find 'Category:' line in response: {response_text}")

        if confidence_match:
            try:
                confidence = float(confidence_match.group(1))
                # Clamp confidence between 0.0 and 1.0
                confidence = max(0.0, min(1.0, confidence))
            except ValueError:
                logger.warning(f"Could not parse confidence value: {confidence_match.group(1)}. Defaulting to 0.0.")
        else:
             logger.warning(f"Could not find 'Confidence:' line in response: {response_text}")

        if reasoning_match:
            reasoning = reasoning_match.group(1).strip()
        else:
            logger.warning(f"Could not find 'Reasoning:' line in response: {response_text}")
            # If reasoning not found, use the whole response text after category/confidence if possible
            lines = response_text.split('\n')
            reasoning_lines = [line for line in lines if not line.lower().startswith('category:') and not line.lower().startswith('confidence:')]
            reasoning = "\n".join(reasoning_lines).strip()
            if not reasoning:
                 reasoning = "Reasoning not provided or parsing failed."

    except Exception as e:
        logger.error(f"Error parsing categorization response: {str(e)}. Response text: {response_text}")
        reasoning = f"Error parsing response: {str(e)}"

    return document_type, confidence, reasoning

def extract_document_features(file_id: str) -> Dict[str, Any]:
    """
    Extract basic features from the document (e.g., file type, size, keywords)
    Placeholder function - needs actual implementation
    """
    # Placeholder: Replace with actual feature extraction logic
    # Example: Use Box API to get file info, maybe extract text snippet
    try:
        client = st.session_state.client
        file_info = client.file(file_id).get(fields=["size", "name", "extension"])
        return {
            "file_size_kb": file_info.size / 1024 if file_info.size else 0,
            "file_extension": file_info.extension.lower() if file_info.extension else "",
            # Add more features like keyword extraction from content if needed
            "keyword_match_score": 0.0 # Placeholder
        }
    except Exception as e:
        logger.warning(f"Could not extract features for file {file_id}: {e}")
        return {
            "file_size_kb": 0,
            "file_extension": "",
            "keyword_match_score": 0.0
        }

def calculate_multi_factor_confidence(ai_confidence: float, features: Dict[str, Any], category: str, reasoning: str, all_categories: List[str]) -> Dict[str, float]:
    """
    Calculate a multi-factor confidence score based on AI confidence, document features, and reasoning quality.
    Placeholder function - needs actual implementation with weighting logic.
    """
    # Placeholder: Simple weighted average - Replace with more sophisticated logic
    weights = {
        "ai_confidence": 0.6,
        "feature_score": 0.2, # Based on file type, size, keywords relevant to category
        "reasoning_quality": 0.2 # Based on length, specificity, keyword presence in reasoning
    }
    
    # 1. AI Confidence (already provided)
    ai_score = ai_confidence
    
    # 2. Feature Score (Example: Higher score if extension matches category expectations)
    feature_score = 0.5 # Default
    ext = features.get("file_extension", "")
    if category == "Invoices" and ext in ["pdf", "docx"]:
        feature_score = 0.8
    elif category == "Financial Report" and ext in ["xlsx", "csv", "pdf"]:
        feature_score = 0.7
    # Add more rules based on features...
    
    # 3. Reasoning Quality (Example: Score based on length and keywords)
    reasoning_quality = 0.5 # Default
    reasoning_len = len(reasoning)
    if reasoning_len > 100:
        reasoning_quality = 0.8
    elif reasoning_len > 50:
        reasoning_quality = 0.6
    # Add checks for keywords relevant to the category in the reasoning...
    
    # Calculate weighted overall score
    overall_confidence = (
        ai_score * weights["ai_confidence"] + 
        feature_score * weights["feature_score"] + 
        reasoning_quality * weights["reasoning_quality"]
    )
    
    # Ensure overall confidence is within [0, 1]
    overall_confidence = max(0.0, min(1.0, overall_confidence))
    
    return {
        "overall": overall_confidence,
        "ai_confidence_factor": ai_score,
        "feature_factor": feature_score,
        "reasoning_factor": reasoning_quality
    }

def apply_confidence_calibration(category: str, confidence: float) -> float:
    """
    Apply calibration adjustments to confidence scores based on historical feedback.
    Placeholder function - needs feedback loop implementation.
    """
    # Placeholder: Load calibration data (e.g., average accuracy per category)
    # calibration_data = load_calibration_data() 
    # adjustment = calibration_data.get(category, 1.0) # Multiplier or offset
    # calibrated_confidence = confidence * adjustment
    # return max(0.0, min(1.0, calibrated_confidence))
    return confidence # No calibration applied in this placeholder

def configure_confidence_thresholds():
    """
    Allow users to configure confidence thresholds for categorization status.
    """
    st.write("Set confidence thresholds to automatically accept, flag for review, or reject categorizations:")
    
    current_thresholds = st.session_state.confidence_thresholds
    
    # Ensure thresholds are logical (auto_accept > verification > rejection)
    auto_accept = st.slider(
        "Auto-Accept Threshold", 
        min_value=0.0, max_value=1.0, 
        value=float(current_thresholds.get("auto_accept", 0.85)), 
        step=0.05,
        key="threshold_auto_accept",
        help="Categories with confidence above this value will be automatically accepted."
    )
    
    verification = st.slider(
        "Verification Threshold", 
        min_value=0.0, max_value=auto_accept, # Max is auto_accept
        value=float(min(current_thresholds.get("verification", 0.6), auto_accept)), 
        step=0.05,
        key="threshold_verification",
        help="Categories with confidence between this value and Auto-Accept need user review."
    )
    
    rejection = st.slider(
        "Rejection Threshold", 
        min_value=0.0, max_value=verification, # Max is verification
        value=float(min(current_thresholds.get("rejection", 0.4), verification)), 
        step=0.05,
        key="threshold_rejection",
        help="Categories with confidence below this value may be flagged or rejected."
    )
    
    # Update session state if changed
    if (auto_accept != current_thresholds.get("auto_accept") or
        verification != current_thresholds.get("verification") or
        rejection != current_thresholds.get("rejection")):
        st.session_state.confidence_thresholds = {
            "auto_accept": auto_accept,
            "verification": verification,
            "rejection": rejection
        }
        logger.info(f"Updated confidence thresholds: {st.session_state.confidence_thresholds}")
        # No rerun needed immediately, changes apply on next categorization or result display

def apply_confidence_thresholds(results: Dict[str, Dict]) -> Dict[str, Dict]:
    """
    Apply status labels (Accepted, Review, Reject) based on confidence thresholds.
    """
    thresholds = st.session_state.confidence_thresholds
    updated_results = {}
    
    for file_id, result in results.items():
        confidence = result.get("calibrated_confidence", result.get("confidence", 0.0))
        
        if confidence >= thresholds["auto_accept"]:
            result["status"] = "Accepted"
        elif confidence >= thresholds["verification"]:
            result["status"] = "Review"
        else:
            # Decide action below verification threshold (e.g., flag as low confidence or reject)
            # For now, just mark as review needed
            result["status"] = "Review (Low Confidence)"
            # Optionally add a specific flag for rejection threshold if needed
            # if confidence < thresholds["rejection"]:
            #     result["status"] = "Rejected (Very Low Confidence)"
        
        updated_results[file_id] = result
        
    return updated_results

def display_confidence_visualization(confidence_data: Dict[str, float]):
    """
    Display a more detailed confidence breakdown using bars.
    """
    overall = confidence_data.get("overall", 0.0)
    ai_factor = confidence_data.get("ai_confidence_factor", 0.0)
    feature_factor = confidence_data.get("feature_factor", 0.0)
    reasoning_factor = confidence_data.get("reasoning_factor", 0.0)
    
    # Determine overall color
    if overall >= 0.8:
        overall_color = "#28a745" # Green
    elif overall >= 0.6:
        overall_color = "#ffc107" # Yellow
    else:
        overall_color = "#dc3545" # Red
        
    st.markdown(f"**Overall Confidence:** <span style='color: {overall_color}; font-weight: bold;'>{overall:.2f}</span>", unsafe_allow_html=True)
    
    # Create data for Altair chart
    data = pd.DataFrame({
        'Factor': ['AI Confidence', 'Document Features', 'Reasoning Quality'],
        'Score': [ai_factor, feature_factor, reasoning_factor]
    })
    
    # Create Altair bar chart
    chart = alt.Chart(data).mark_bar().encode(
        x=alt.X("Score:Q", scale=alt.Scale(domain=[0, 1])), # Set scale domain 0-1
        y=alt.Y("Factor:N", sort="-x"), # Sort bars by score descending
        tooltip=['Factor', alt.Tooltip('Score', format=".2f")]
    ).properties(
        title='Confidence Factors'
    )
    
    st.altair_chart(chart, use_container_width=True)

def get_confidence_explanation(confidence_data: Dict[str, float], category: str) -> Dict[str, str]:
    """
    Generate human-readable explanations for the confidence score.
    """
    overall = confidence_data.get("overall", 0.0)
    ai_factor = confidence_data.get("ai_confidence_factor", 0.0)
    feature_factor = confidence_data.get("feature_factor", 0.0)
    reasoning_factor = confidence_data.get("reasoning_factor", 0.0)
    
    explanation = f"The overall confidence score of {overall:.2f} for category '{category}' is based on several factors:"
    
    # AI Confidence Explanation
    if ai_factor >= 0.8:
        explanation += f"\n- The AI model reported high confidence ({ai_factor:.2f}) in its initial assessment."
    elif ai_factor >= 0.6:
        explanation += f"\n- The AI model reported medium confidence ({ai_factor:.2f})."
    else:
        explanation += f"\n- The AI model reported low confidence ({ai_factor:.2f}), suggesting some uncertainty."
        
    # Feature Factor Explanation
    if feature_factor >= 0.7:
        explanation += f"\n- Document features (like file type, size) strongly align ({feature_factor:.2f}) with typical '{category}' documents."
    elif feature_factor >= 0.5:
        explanation += f"\n- Document features moderately align ({feature_factor:.2f}) with '{category}' documents."
    else:
        explanation += f"\n- Document features show low alignment ({feature_factor:.2f}) with typical '{category}' documents."
        
    # Reasoning Quality Explanation
    if reasoning_factor >= 0.7:
        explanation += f"\n- The AI's reasoning was detailed and specific ({reasoning_factor:.2f})."
    elif reasoning_factor >= 0.5:
        explanation += f"\n- The AI's reasoning was moderately detailed ({reasoning_factor:.2f})."
    else:
        explanation += f"\n- The AI's reasoning lacked detail or specificity ({reasoning_factor:.2f})."
        
    return {"overall": explanation}

def validate_confidence_with_examples():
    """
    Provide examples and allow testing of confidence calculation logic.
    """
    st.write("Test the multi-factor confidence calculation with example inputs:")
    
    # Example inputs
    example_ai_confidence = st.slider("Example AI Confidence", 0.0, 1.0, 0.75, 0.05)
    example_file_ext = st.selectbox("Example File Extension", ["pdf", "docx", "xlsx", "jpg", "txt", ""])
    example_reasoning = st.text_area("Example AI Reasoning", "The document contains tables, financial figures, and mentions 'Q3 results'.")
    example_category = st.selectbox("Example Category", [dtype['name'] for dtype in st.session_state.document_types])
    
    # Simulate feature extraction
    example_features = {
        "file_size_kb": 500,
        "file_extension": example_file_ext,
        "keyword_match_score": 0.6 # Placeholder
    }
    
    # Calculate confidence
    calculated_confidence = calculate_multi_factor_confidence(
        example_ai_confidence,
        example_features,
        example_category,
        example_reasoning,
        [dtype['name'] for dtype in st.session_state.document_types]
    )
    
    # Display results
    st.write("**Calculated Multi-Factor Confidence:**")
    display_confidence_visualization(calculated_confidence)
    explanation = get_confidence_explanation(calculated_confidence, example_category)
    st.info(explanation["overall"])

def save_categorization_feedback(file_id: str, original_category: str, corrected_category: str):
    """
    Save user feedback on categorization for future calibration.
    Placeholder function - needs persistent storage.
    """
    feedback_entry = {
        "file_id": file_id,
        "original_category": original_category,
        "corrected_category": corrected_category,
        "timestamp": datetime.datetime.now().isoformat()
    }
    logger.info(f"Saving feedback: {feedback_entry}")
    # Placeholder: Append to a file or database
    # with open("categorization_feedback.jsonl", "a") as f:
    #     f.write(json.dumps(feedback_entry) + "\n")
    st.toast("Feedback saved for improving future categorizations.")

def combine_categorization_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Combine results from multiple models using weighted voting or averaging.
    Placeholder: Simple majority vote for now.
    """
    if not results:
        return {"document_type": "Other", "confidence": 0.0, "reasoning": "No results to combine"}

    votes = {}
    total_confidence = 0
    combined_reasoning = "Combined Reasoning:\n"

    for result in results:
        category = result.get("document_type", "Other")
        confidence = result.get("confidence", 0.0)
        reasoning = result.get("reasoning", "")
        
        votes[category] = votes.get(category, 0) + 1 # Simple count for majority
        total_confidence += confidence # Simple sum for averaging later
        combined_reasoning += f"- Model Result: {category} (Conf: {confidence:.2f})\n  Reasoning: {reasoning}\n"

    # Determine winning category by majority vote
    if votes:
        winning_category = max(votes, key=votes.get)
        # Calculate average confidence for the winning category (or overall average)
        avg_confidence = total_confidence / len(results) if results else 0.0
    else:
        winning_category = "Other"
        avg_confidence = 0.0

    return {
        "document_type": winning_category,
        "confidence": avg_confidence, # Use average confidence
        "reasoning": combined_reasoning
    }

# --- Helper functions (like get_document_preview_url) would go here ---
# Placeholder for get_document_preview_url
def get_document_preview_url(file_id: str) -> Optional[str]:
    """Placeholder: Get a preview URL for the document."""
    # In a real scenario, this might involve generating a temporary preview link
    # or using a service that provides previews.
    logger.info(f"Preview requested for file {file_id}, but feature is not implemented.")
    return None

# Placeholder for collect_user_feedback
def collect_user_feedback(file_id: str, result: Dict):
    """Placeholder: UI elements for collecting detailed user feedback."""
    st.write("Feedback collection UI not implemented.")

# Placeholder for confidence calibration loading
def load_calibration_data() -> Dict:
     """Placeholder: Load calibration data from storage."""
     return {}

