# Merged version of direct_metadata_application_v3_fixed.py
# Incorporates bug fixes (strict type conversion, confidence filtering assurance)
# Restores per-file template mapping logic based on document categorization.
# Corrects template ID parsing for FULL scope and simple key.
# Corrects metadata update method using SDK operations pattern.
# Preserves the original structure and UI elements.
# ADDED: Fallback to global.properties if no custom template is found.

import streamlit as st
import logging
import json
from boxsdk import Client, exception
from boxsdk.object.metadata import MetadataUpdate # Import MetadataUpdate
from dateutil import parser
from datetime import timezone

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Cache for template schemas to avoid repeated API calls
if 'template_schema_cache' not in st.session_state:
    st.session_state.template_schema_cache = {}

# Define a custom exception for conversion errors (from the fix)
class ConversionError(ValueError):
    pass

def get_template_schema(client, full_scope, template_key):
    """
    Fetches the metadata template schema from Box API (compatible with SDK v3.x).
    Uses a cache to avoid redundant API calls.
    Uses FULL scope (e.g., enterprise_12345) and simple template key.
    
    Args:
        client: Box client object
        full_scope (str): The full scope identifier (e.g., "enterprise_12345" or "global").
        template_key (str): The key of the template (e.g., "homeLoan").
        
    Returns:
        dict: A dictionary mapping field keys to their types, or None if error.
    """
    # --- No changes needed here --- 
    cache_key = f'{full_scope}_{template_key}' 
    if cache_key in st.session_state.template_schema_cache:
        logger.info(f"Using cached schema for {full_scope}/{template_key}")
        return st.session_state.template_schema_cache[cache_key]

    try:
        logger.info(f"Fetching template schema for {full_scope}/{template_key}")
        template = client.metadata_template(full_scope, template_key).get()
        
        if template and hasattr(template, 'fields') and template.fields:
            schema_map = {field['key']: field['type'] for field in template.fields}
            st.session_state.template_schema_cache[cache_key] = schema_map
            logger.info(f"Successfully fetched and cached schema for {full_scope}/{template_key}")
            return schema_map
        else:
            logger.warning(f"Template {full_scope}/{template_key} found but has no fields or is invalid.")
            st.session_state.template_schema_cache[cache_key] = {}
            return {}
            
    except exception.BoxAPIException as e:
        logger.error(f"Box API Error fetching template schema for {full_scope}/{template_key}: Status={e.status}, Code={e.code}, Message={e.message}")
        st.session_state.template_schema_cache[cache_key] = None 
        return None
    except Exception as e:
        logger.exception(f"Unexpected error fetching template schema for {full_scope}/{template_key}: {e}")
        st.session_state.template_schema_cache[cache_key] = None
        return None

def convert_value_for_template(key, value, field_type):
    """
    Converts a metadata value to the type specified by the template field.
    Raises ConversionError if conversion fails. (Modified from original to be strict)
    """
    # --- No changes needed here --- 
    if value is None:
        return None 
        
    original_value_repr = repr(value) # For logging

    try:
        if field_type == 'float':
            if isinstance(value, str):
                cleaned_value = value.replace('$', '').replace(',', '')
                try:
                    return float(cleaned_value)
                except ValueError:
                    raise ConversionError(f"Could not convert string '{value}' to float for key '{key}'.")
            elif isinstance(value, (int, float)):
                return float(value)
            else:
                 raise ConversionError(f"Value {original_value_repr} for key '{key}' is not a string or number, cannot convert to float.")
                 
        elif field_type == 'date':
            if isinstance(value, str):
                try:
                    dt = parser.parse(value)
                    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        dt = dt.astimezone(timezone.utc)
                    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                except (parser.ParserError, ValueError) as e:
                    raise ConversionError(f"Could not parse date string '{value}' for key '{key}': {e}.")
            else:
                raise ConversionError(f"Value {original_value_repr} for key '{key}' is not a string, cannot convert to date.")
                
        elif field_type == 'string' or field_type == 'enum':
            if not isinstance(value, str):
                logger.info(f"Converting value {original_value_repr} to string for key '{key}' (type {field_type}).")
            return str(value)
            
        elif field_type == 'multiSelect':
            if isinstance(value, list):
                converted_list = [str(item) for item in value]
                if converted_list != value:
                     logger.info(f"Converting items in list {original_value_repr} to string for key '{key}' (type multiSelect).")
                return converted_list
            elif isinstance(value, str):
                logger.info(f"Converting string value {original_value_repr} to list of strings for key '{key}' (type multiSelect).")
                return [value]
            else:
                logger.info(f"Converting value {original_value_repr} to list of strings for key '{key}' (type multiSelect).")
                return [str(value)]
                
        else:
            logger.warning(f"Unknown field type '{field_type}' for key '{key}'. Cannot convert value {original_value_repr}.")
            raise ConversionError(f"Unknown field type '{field_type}' for key '{key}'.")
            
    except ConversionError: # Re-raise specific error
        raise
    except Exception as e: # Catch unexpected errors during conversion
        logger.error(f"Unexpected error converting value {original_value_repr} for key '{key}' (type {field_type}): {e}.")
        raise ConversionError(f"Unexpected error converting value for key '{key}': {e}")

def fix_metadata_format(metadata_values):
    """
    Fix the metadata format by converting string representations of dictionaries
    to actual Python dictionaries.
    """
    # --- No changes needed here --- 
    formatted_metadata = {}
    for key, value in metadata_values.items():
        if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
            try:
                json_compatible_str = value.replace("'", '"')
                parsed_value = json.loads(json_compatible_str)
                formatted_metadata[key] = parsed_value
            except json.JSONDecodeError:
                formatted_metadata[key] = value
        else:
            formatted_metadata[key] = value
    return formatted_metadata

def flatten_metadata_for_template(metadata_values):
    """
    Flatten the metadata structure if needed (e.g., extracting from 'answer').
    """
    # --- No changes needed here --- 
    flattened_metadata = {}
    if 'answer' in metadata_values and isinstance(metadata_values['answer'], dict):
        for key, value in metadata_values['answer'].items():
            flattened_metadata[key] = value
    else:
        flattened_metadata = metadata_values.copy()
        
    keys_to_remove = ['ai_agent_info', 'created_at', 'completion_reason', 'answer']
    for key in keys_to_remove:
        if key in flattened_metadata:
            del flattened_metadata[key]
    return flattened_metadata

def filter_confidence_fields(metadata_values):
    """
    Filter out confidence score fields (keys ending with "_confidence").
    """
    # --- No changes needed here --- 
    return {key: value for key, value in metadata_values.items() if not key.endswith("_confidence")} 

def parse_template_id(template_id_full):
    """ 
    Parses 'scope_templateKey' (e.g., 'enterprise_12345_myTemplate') into 
    (full_scope, template_key).
    Corrected based on user feedback.
    
    Args:
        template_id_full (str): The combined template ID string.
        
    Returns:
        tuple: (full_scope, template_key)
               full_scope (str): The full scope identifier (e.g., 'enterprise_12345' or 'global')
               template_key (str): The actual key of the template (e.g., 'myTemplate')
    Raises:
        ValueError: If the format is invalid.
    """
    # --- No changes needed here --- 
    if not template_id_full or '_' not in template_id_full:
        raise ValueError(f"Invalid template ID format: {template_id_full}")
    
    last_underscore_index = template_id_full.rfind('_')
    if last_underscore_index == 0 or last_underscore_index == len(template_id_full) - 1:
        raise ValueError(f"Template ID format incorrect, expected scope_templateKey: {template_id_full}")
        
    full_scope = template_id_full[:last_underscore_index]
    template_key = template_id_full[last_underscore_index + 1:]
    
    if not full_scope.startswith('enterprise_') and full_scope != 'global':
         if not full_scope == 'enterprise': 
            logger.warning(f"Scope format '{full_scope}' might be unexpected. Expected 'enterprise_...' or 'global'.")
        
    logger.debug(f"Parsed template ID '{template_id_full}' -> full_scope='{full_scope}', template_key='{template_key}'")
    return full_scope, template_key

def apply_metadata_to_file_direct(client, file_id, file_name, metadata_values, full_scope, template_key):
    """
    Applies metadata to a single file using the correct SDK update pattern.
    Uses FULL scope and simple template key.
    Handles both custom templates and the global.properties fallback.
    (Internal function called by apply_metadata_direct)
    
    Args:
        client: Box client object
        file_id (str): ID of the file.
        file_name (str): Name of the file.
        metadata_values (dict): Extracted metadata (before filtering/conversion).
        full_scope (str): The full scope identifier (e.g., 'enterprise_12345' or 'global').
        template_key (str): The actual template key (e.g., 'homeLoan' or 'properties').
        
    Returns:
        tuple: (success_flag, message_string)
    """
    logger.info(f"Starting metadata application for file ID {file_id} ({file_name}) with template {full_scope}/{template_key}")
    
    is_global_properties = (full_scope == 'global' and template_key == 'properties')
    
    try:
        filtered_metadata = filter_confidence_fields(metadata_values) 
        logger.debug(f"File ID {file_id}: Filtered metadata (no confidence): {filtered_metadata}")

        metadata_to_apply = {}
        conversion_errors = []

        if is_global_properties:
            logger.info(f"Applying to global.properties for file {file_id}. Skipping schema validation and type conversion.")
            for key, value in filtered_metadata.items():
                if value is None:
                    continue
                if isinstance(value, (str, int, float, bool)):
                    metadata_to_apply[key] = value
                else:
                    try:
                        metadata_to_apply[key] = str(value)
                        logger.info(f"Converted value for key '{key}' to string for global.properties.")
                    except Exception as str_e:
                        error_msg = f"Could not convert value for key '{key}' to string for global.properties: {str_e}. Field skipped."
                        logger.warning(error_msg)
                        conversion_errors.append(error_msg)
        else:
            template_schema = get_template_schema(client, full_scope, template_key)
            if template_schema is None:
                error_msg = f"Could not retrieve template schema for {full_scope}/{template_key}. Cannot apply metadata to file {file_id} ({file_name})."
                st.error(f"Schema retrieval failed for template '{template_key}'. Cannot apply metadata to {file_name}. Check template key and permissions.")
                return False, error_msg
            if not template_schema:
                 logger.warning(f"Template schema for {full_scope}/{template_key} is empty. No fields to apply for file {file_id} ({file_name}).")
                 st.info(f"Template '{template_key}' has no fields. Nothing to apply to {file_name}.")
                 return True, "Template schema is empty, nothing to apply."

            for key, field_type in template_schema.items():
                if key in filtered_metadata:
                    value = filtered_metadata[key]
                    try:
                        converted_value = convert_value_for_template(key, value, field_type)
                        if converted_value is not None:
                            metadata_to_apply[key] = converted_value
                        else:
                            logger.info(f"Value for key '{key}' is None after conversion. Skipping for file {file_id}.")
                    except ConversionError as e:
                        error_msg = f"Conversion error for key '{key}' (expected type '{field_type}', value: {repr(value)}): {e}. Field skipped."
                        logger.warning(error_msg)
                        conversion_errors.append(error_msg)
                    except Exception as e:
                        error_msg = f"Unexpected error processing key '{key}' for file {file_id}: {e}. Field skipped."
                        logger.error(error_msg)
                        conversion_errors.append(error_msg)
                else:
                    logger.info(f"Template field '{key}' not found in extracted metadata for file {file_id}. Skipping field.")

        if not metadata_to_apply:
            if conversion_errors:
                warn_msg = f"Metadata application skipped for file {file_name}: No fields could be successfully converted or prepared. Errors: {'; '.join(conversion_errors)}"
                st.warning(warn_msg)
                logger.warning(warn_msg)
                return False, f"No valid metadata fields to apply after conversion/preparation errors: {'; '.join(conversion_errors)}"
            else:
                info_msg = f"No matching metadata fields found or all values were None for file {file_name}. Nothing to apply."
                st.info(info_msg)
                logger.info(info_msg)
                return True, "No matching fields to apply"

        logger.info(f"Attempting to apply metadata to file {file_id} using template {full_scope}/{template_key} with payload: {metadata_to_apply}")
        try:
            metadata_instance = client.file(file_id).metadata(scope=full_scope, template=template_key)
            
            try:
                created_metadata = metadata_instance.create(metadata_to_apply)
                logger.info(f"Successfully created new metadata for file {file_id}: {created_metadata}")
                st.success(f"Successfully applied metadata to {file_name} using template {template_key}.")
                return True, f"Successfully applied metadata to {file_name}."
            except exception.BoxAPIException as e:
                if e.status == 409: 
                    logger.info(f"Metadata instance already exists for file {file_id} and template {full_scope}/{template_key}. Attempting to update.")
                    try:
                        if is_global_properties:
                            logger.info(f"Updating global.properties for file {file_id} directly with payload: {metadata_to_apply}")
                            updated_metadata = metadata_instance.update(metadata_to_apply)
                        else:
                            logger.info(f"Updating structured template {full_scope}/{template_key} for file {file_id} using MetadataUpdate operations with payload: {metadata_to_apply}")
                            update_request = MetadataUpdate()
                            for key_to_update, value_to_update in metadata_to_apply.items():
                                update_request.add_update(path=f"/{key_to_update}", value=value_to_update)
                            updated_metadata = metadata_instance.update(update_request)
                        
                        logger.info(f"Successfully updated existing metadata for file {file_id}: {updated_metadata}")
                        st.success(f"Successfully updated metadata on {file_name} using template {template_key}.")
                        return True, f"Successfully updated metadata for {file_name}."
                    except exception.BoxAPIException as update_e:
                        error_msg = f"Failed to update existing metadata for file {file_id} ({file_name}): {update_e.message}"
                        logger.error(error_msg)
                        st.error(f"Failed to update metadata on {file_name}: {update_e.message}")
                        return False, error_msg
                    except Exception as update_gen_e:
                        error_msg = f"Unexpected error updating metadata for file {file_id} ({file_name}): {update_gen_e}"
                        logger.exception(error_msg)
                        st.error(f"Unexpected error updating metadata on {file_name}.")
                        return False, error_msg
                else:
                    error_msg = f"Failed to create metadata for file {file_id} ({file_name}): {e.message}"
                    logger.error(error_msg)
                    st.error(f"Failed to apply metadata to {file_name}: {e.message}")
                    return False, error_msg
        except exception.BoxAPIException as e:
            error_msg = f"Box API error during metadata application for file {file_id} ({file_name}): {e.message}"
            logger.error(error_msg)
            st.error(f"Box API error applying metadata to {file_name}: {e.message}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error during metadata application for file {file_id} ({file_name}): {e}"
            logger.exception(error_msg)
            st.error(f"An unexpected error occurred while applying metadata to {file_name}.")
            return False, error_msg

def apply_metadata_direct(client, selected_files_data, metadata_results, template_mappings, default_template_id, use_direct_json_input, direct_json_input):
    """
    Main function to apply metadata to selected files based on UI inputs.
    Handles per-file template mapping or a default template.
    (This is the main entry point called by the Streamlit app)
    """
    if not selected_files_data:
        st.warning("No files selected for metadata application.")
        return

    if not client:
        st.error("Box client is not initialized. Cannot apply metadata.")
        return

    overall_success_count = 0
    overall_failure_count = 0
    results_summary = []

    for file_data in selected_files_data:
        file_id = file_data['id']
        file_name = file_data['name']
        doc_category = file_data.get('doc_category', 'Unknown') # Get category or default

        current_metadata_values = None
        current_full_scope = None
        current_template_key = None

        if use_direct_json_input:
            logger.info(f"Using direct JSON input for file {file_id} ({file_name}).")
            try:
                # Use the already parsed direct_json_input if available and valid
                if isinstance(direct_json_input, dict):
                    current_metadata_values = direct_json_input
                else:
                    current_metadata_values = json.loads(direct_json_input) # Assuming direct_json_input is a string here
                
                # For direct JSON, we assume global.properties unless a specific template is part of the JSON structure (advanced)
                # Or, if a default template is provided and we want to apply to it.
                # For simplicity now, assume direct JSON might be free-form or target a specific template if default_template_id is set.
                if default_template_id:
                    try:
                        current_full_scope, current_template_key = parse_template_id(default_template_id)
                        logger.info(f"Direct JSON input will be applied to template: {current_full_scope}/{current_template_key}")
                    except ValueError as e:
                        st.error(f"Invalid default template ID format for direct JSON: {default_template_id}. Error: {e}")
                        results_summary.append({'file_name': file_name, 'status': 'Error', 'message': f"Invalid default template ID: {e}"}) 
                        overall_failure_count += 1
                        continue # Skip this file
                else: # Fallback to global.properties for direct JSON if no default template specified
                    current_full_scope = "global"
                    current_template_key = "properties"
                    logger.info(f"Direct JSON input will be applied to global.properties for file {file_id}")

            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON input: {e}. Cannot apply metadata to {file_name}.")
                results_summary.append({'file_name': file_name, 'status': 'Error', 'message': f"Invalid JSON input: {e}"})
                overall_failure_count += 1
                continue # Skip this file
            except Exception as e: # Catch any other error during direct JSON processing
                st.error(f"Error processing direct JSON input for {file_name}: {e}")
                results_summary.append({'file_name': file_name, 'status': 'Error', 'message': f"Error processing direct JSON: {e}"})
                overall_failure_count += 1
                continue
        else:
            # Use AI extracted metadata results
            if file_id not in metadata_results or not metadata_results[file_id].get('extracted_metadata'):
                st.warning(f"No extracted metadata found for {file_name} (ID: {file_id}). Skipping.")
                results_summary.append({'file_name': file_name, 'status': 'Skipped', 'message': 'No extracted metadata available.'})
                continue # Skip this file
            
            current_metadata_values = metadata_results[file_id]['extracted_metadata']
            
            # Determine template: per-file mapping or default
            template_id_to_use = default_template_id
            if template_mappings and doc_category in template_mappings and template_mappings[doc_category]:
                template_id_to_use = template_mappings[doc_category]
                logger.info(f"Using mapped template '{template_id_to_use}' for file {file_name} (category: {doc_category})")
            elif not default_template_id:
                 # Fallback to global.properties if no mapping and no default
                logger.info(f"No specific template mapping for category '{doc_category}' and no default template. Falling back to global.properties for {file_name}.")
                current_full_scope = "global"
                current_template_key = "properties"
            else:
                logger.info(f"Using default template '{default_template_id}' for file {file_name} (category: {doc_category})")

            if not current_full_scope: # If not already set to global.properties fallback
                try:
                    current_full_scope, current_template_key = parse_template_id(template_id_to_use)
                except ValueError as e:
                    st.error(f"Invalid template ID format '{template_id_to_use}' for {file_name}. Error: {e}")
                    results_summary.append({'file_name': file_name, 'status': 'Error', 'message': f"Invalid template ID '{template_id_to_use}': {e}"})
                    overall_failure_count += 1
                    continue # Skip this file

        # Pre-process and flatten metadata (common for both direct JSON and AI extracted)
        if not isinstance(current_metadata_values, dict):
            logger.error(f"Metadata values for {file_name} are not a dictionary: {current_metadata_values}")
            st.error(f"Internal error: metadata for {file_name} is not in the expected format. Skipping.")
            results_summary.append({'file_name': file_name, 'status': 'Error', 'message': 'Metadata not in dict format.'})
            overall_failure_count += 1
            continue

        current_metadata_values = fix_metadata_format(current_metadata_values)
        current_metadata_values = flatten_metadata_for_template(current_metadata_values)

        if not current_metadata_values:
            st.info(f"No metadata to apply for {file_name} after pre-processing. Skipping.")
            results_summary.append({'file_name': file_name, 'status': 'Skipped', 'message': 'No metadata after pre-processing.'})
            continue

        # Apply to the file
        success, message = apply_metadata_to_file_direct(
            client,
            file_id,
            file_name,
            current_metadata_values,
            current_full_scope,
            current_template_key
        )

        if success:
            overall_success_count += 1
            results_summary.append({'file_name': file_name, 'status': 'Success', 'message': message})
        else:
            overall_failure_count += 1
            results_summary.append({'file_name': file_name, 'status': 'Failure', 'message': message})
    
    # Display summary
    st.subheader("Metadata Application Summary")
    if overall_success_count > 0:
        st.success(f"Successfully applied/updated metadata for {overall_success_count} file(s).")
    if overall_failure_count > 0:
        st.error(f"Failed to apply/update metadata for {overall_failure_count} file(s).")
    
    # Display detailed results in a more structured way if needed
    if results_summary:
        st.dataframe(results_summary)

    logger.info(f"Metadata application process finished. Success: {overall_success_count}, Failure: {overall_failure_count}")

# Example of how this might be called (for testing or integration context)
# This part would typically be in your main Streamlit app.py
if __name__ == '__main__':
    # Mock objects for testing - replace with actual objects in your app
    mock_client = None # Replace with an actual Box Client
    mock_selected_files = [{'id': '12345', 'name': 'TestFile1.pdf', 'doc_category': 'Invoice'},
                           {'id': '67890', 'name': 'TestFile2.docx', 'doc_category': 'Contract'}]
    mock_metadata_results = {
        '12345': {'extracted_metadata': {'InvoiceNumber': 'INV-001', 'Amount': '100.50', 'Vendor': 'TestVendor'}},
        '67890': {'extracted_metadata': {'ContractValue': '5000', 'EffectiveDate': '2024-01-01', 'PartyA': 'Client Corp'}}
    }
    mock_template_mappings = {'Invoice': 'enterprise_123_invoiceTemplate', 'Contract': 'enterprise_123_contractTemplate'}
    mock_default_template_id = "global_properties" # Or a specific template like 'enterprise_123_defaultDoc'
    
    # Simulate Streamlit UI elements for testing
    st.title("Metadata Application Test")
    use_direct_json = st.checkbox("Use Direct JSON Input", False)
    direct_json_str = "{}"
    if use_direct_json:
        direct_json_str = st.text_area("Enter JSON Metadata", value='{"customField1": "customValue1"}')

    if st.button("Apply Metadata"):
        parsed_direct_json = None
        if use_direct_json:
            try:
                parsed_direct_json = json.loads(direct_json_str)
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")
                # In a real app, you might prevent further execution or handle this more gracefully
        
        # apply_metadata_direct(
        #     mock_client, 
        #     mock_selected_files, 
        #     mock_metadata_results, 
        #     mock_template_mappings, 
        #     mock_default_template_id,
        #     use_direct_json,
        #     parsed_direct_json # Pass the parsed dictionary
        # )
        st.write("Test run complete (actual call commented out as mock_client is None).")
        st.write("To run this test, provide a valid Box Client and uncomment the call.")
