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
    logger.info("Starting direct metadata application process...")
    if not selected_files_data:
        st.warning("No files selected for metadata application.")
        return

    if use_direct_json_input:
        if not direct_json_input:
            st.error("JSON input is selected, but no JSON data provided.")
            return
        try:
            # Attempt to parse the JSON input for all files
            common_metadata_from_json = json.loads(direct_json_input)
            if not isinstance(common_metadata_from_json, dict):
                st.error("JSON input must be a valid JSON object (dictionary).")
                return
            logger.info(f"Using common metadata from direct JSON input: {common_metadata_from_json}")
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON input: {e}. Please provide a valid JSON object.")
            return
    else:
        if not metadata_results:
            st.warning("No metadata results available from AI extraction to apply.")
            return
        common_metadata_from_json = None # Not using direct JSON

    overall_success_count = 0
    overall_error_count = 0
    results_summary = [] # To store (file_name, status, message)

    for file_data in selected_files_data:
        file_id = file_data['id']
        file_name = file_data['name']
        logger.info(f"Processing file: {file_name} (ID: {file_id})")

        current_metadata_values = {}
        if use_direct_json_input:
            current_metadata_values = common_metadata_from_json.copy()
            logger.info(f"Using direct JSON input for file {file_name}")
        elif file_id in metadata_results:
            # Use AI extracted metadata, flatten and fix format
            raw_extracted_metadata = metadata_results[file_id].get('extracted_metadata', {})
            fixed_format_metadata = fix_metadata_format(raw_extracted_metadata)
            current_metadata_values = flatten_metadata_for_template(fixed_format_metadata)
            logger.info(f"Using AI extracted metadata for file {file_name}: {current_metadata_values}")
        else:
            logger.warning(f"No metadata found for file {file_name} (ID: {file_id}) in AI results. Skipping.")
            results_summary.append((file_name, "Skipped", "No AI metadata available."))
            continue

        if not current_metadata_values:
            logger.warning(f"No metadata values to apply for file {file_name} after processing. Skipping.")
            results_summary.append((file_name, "Skipped", "No metadata to apply after processing."))
            continue

        # Determine the template to use for this file
        chosen_template_id = default_template_id
        if template_mappings and file_id in template_mappings and template_mappings[file_id]:
            chosen_template_id = template_mappings[file_id]
            logger.info(f"Using mapped template '{chosen_template_id}' for file {file_name}.")
        else:
            logger.info(f"Using default template '{chosen_template_id}' for file {file_name}.")

        if not chosen_template_id:
            logger.error(f"No template ID determined for file {file_name}. Cannot apply metadata.")
            st.error(f"Critical error: No template ID for {file_name}. Skipping.")
            results_summary.append((file_name, "Error", "No template ID determined."))
            overall_error_count += 1
            continue
        
        try:
            full_scope, template_key = parse_template_id(chosen_template_id)
        except ValueError as e:
            logger.error(f"Invalid template ID format '{chosen_template_id}' for file {file_name}: {e}")
            st.error(f"Invalid template ID format '{chosen_template_id}' for {file_name}. Skipping.")
            results_summary.append((file_name, "Error", f"Invalid template ID: {e}"))
            overall_error_count += 1
            continue

        # Call the internal function to apply metadata to the single file
        success, message = apply_metadata_to_file_direct(
            client,
            file_id,
            file_name,
            current_metadata_values, 
            full_scope, 
            template_key
        )

        if success:
            overall_success_count += 1
            results_summary.append((file_name, "Success", message))
        else:
            overall_error_count += 1
            results_summary.append((file_name, "Error", message))

    # Display summary of operations
    st.subheader("Metadata Application Summary")
    if results_summary:
        for name, status, msg in results_summary:
            if status == "Success":
                st.success(f"{name}: {status} - {msg}")
            elif status == "Error":
                st.error(f"{name}: {status} - {msg}")
            else:
                st.info(f"{name}: {status} - {msg}")
    
    if overall_success_count > 0:
        st.balloons()
        st.success(f"Successfully applied/updated metadata for {overall_success_count} file(s).")
    if overall_error_count > 0:
        st.error(f"Failed to apply/update metadata for {overall_error_count} file(s). Check logs for details.")
    if not selected_files_data:
        st.info("No files were processed.")

    logger.info(f"Direct metadata application process finished. Success: {overall_success_count}, Errors: {overall_error_count}")

# Example of how this might be called (for testing or if run standalone)
if __name__ == '__main__':
    # This is a placeholder for testing and would require a mock client and data.
    # In the Streamlit app, this module is imported and functions are called directly.
    st.title("Metadata Application Module (Test Mode)")
    logger.info("Module run in test mode.")

    # Mock Box Client (replace with actual client for real use)
    class MockBoxClient:
        def file(self, file_id):
            logger.info(f"MockBoxClient: file(file_id='{file_id}') called")
            return MockFile(file_id, self)
        def metadata_template(self, scope, template_key):
            logger.info(f"MockBoxClient: metadata_template(scope='{scope}', template_key='{template_key}') called")
            if scope == "global" and template_key == "properties":
                 return MockMetadataTemplate(scope, template_key, fields=[]) # No schema for global
            if scope == "enterprise_123" and template_key == "testTemplate":
                return MockMetadataTemplate(scope, template_key, fields=[
                    {'key': 'description', 'type': 'string'},
                    {'key': 'amount', 'type': 'float'},
                    {'key': 'docDate', 'type': 'date'}
                ])
            raise exception.BoxAPIException(status=404, message="Template not found")

    class MockFile:
        def __init__(self, file_id, client):
            self.id = file_id
            self._client = client
            self._metadata_instances = {}
            logger.info(f"MockFile created for ID: {self.id}")

        def metadata(self, scope, template):
            logger.info(f"MockFile: metadata(scope='{scope}', template='{template}') called for file ID {self.id}")
            key = f"{scope}_{template}"
            if key not in self._metadata_instances:
                self._metadata_instances[key] = MockMetadataInstance(self, scope, template, self._client)
            return self._metadata_instances[key]

    class MockMetadataTemplate:
        def __init__(self, scope, template_key, fields):
            self.scope = scope
            self.template_key = template_key
            self.fields = fields
            logger.info(f"MockMetadataTemplate created: {scope}/{template_key} with fields: {fields}")
        def get(self):
            logger.info(f"MockMetadataTemplate: get() called for {self.scope}/{self.template_key}")
            return self # Return self as the get() method in SDK returns the template object

    class MockMetadataInstance:
        def __init__(self, file_obj, scope, template, client):
            self._file = file_obj
            self.scope = scope
            self.template = template
            self._client = client
            self._data = None # Stores the actual metadata
            self._exists = False
            logger.info(f"MockMetadataInstance created for file {file_obj.id}, template {scope}/{template}")

        def create(self, metadata):
            logger.info(f"MockMetadataInstance: create() called with {metadata} for file {self._file.id}")
            if self._exists:
                raise exception.BoxAPIException(status=409, message="Metadata instance already exists")
            self._data = metadata
            self._exists = True
            logger.info(f"MockMetadataInstance: created data {self._data}")
            return self._data # Return the applied metadata

        def update(self, metadata_update_obj_or_dict):
            logger.info(f"MockMetadataInstance: update() called with {metadata_update_obj_or_dict} for file {self._file.id}")
            if not self._exists:
                # This case might not happen if create is always tried first
                # but good to simulate for robustness
                raise exception.BoxAPIException(status=404, message="Metadata instance not found, cannot update")
            
            if isinstance(metadata_update_obj_or_dict, MetadataUpdate):
                # Simulate applying operations from MetadataUpdate
                if self._data is None: self._data = {}
                for op in metadata_update_obj_or_dict.get_updates():
                    # Simplified: only handles 'add' and 'replace' which are similar here
                    # Path is like "/fieldName"
                    key = op['path'][1:] 
                    self._data[key] = op['value']
                logger.info(f"MockMetadataInstance: updated data (from MetadataUpdate) to {self._data}")
            elif isinstance(metadata_update_obj_or_dict, dict):
                # Direct dictionary update (for global.properties)
                if self._data is None: self._data = {}
                self._data.update(metadata_update_obj_or_dict)
                logger.info(f"MockMetadataInstance: updated data (from dict) to {self._data}")
            else:
                raise ValueError("Invalid type for metadata update")
            return self._data # Return the updated metadata

    # --- Test Data ---
    mock_client = MockBoxClient()
    mock_selected_files = [
        {'id': 'file123', 'name': 'TestDocument1.pdf'},
        {'id': 'file456', 'name': 'AnotherDoc.docx'}
    ]
    mock_ai_results = {
        'file123': {
            'extracted_metadata': {
                'description': 'This is a test document.',
                'amount': '123.45',
                'docDate': '2023-10-26T10:00:00Z',
                'custom_field_confidence': 0.9
            }
        },
        'file456': {
            'extracted_metadata': {
                'loanID': 'L001',
                'applicantName': 'John Doe',
                'status': 'Pending'
            }
        }
    }
    mock_template_mappings = {
        'file123': 'enterprise_123_testTemplate'
    }
    default_template_id_test = 'global_properties' # Fallback for file456

    st.sidebar.header("Test Controls")
    run_test = st.sidebar.button("Run Test Application")

    if run_test:
        st.subheader("Test Run Output:")
        apply_metadata_direct(
            client=mock_client, 
            selected_files_data=mock_selected_files, 
            metadata_results=mock_ai_results, 
            template_mappings=mock_template_mappings, 
            default_template_id=default_template_id_test,
            use_direct_json_input=False,
            direct_json_input=""
        )

        st.info("Test with direct JSON input (global.properties):")
        direct_json_test = {"project": "Alpha", "version": "1.1"}
        apply_metadata_direct(
            client=mock_client, 
            selected_files_data=[mock_selected_files[0]], # Just one file
            metadata_results={}, 
            template_mappings={}, 
            default_template_id='global_properties',
            use_direct_json_input=True,
            direct_json_input=json.dumps(direct_json_test)
        )

        st.info("Test with direct JSON input (structured template):")
        direct_json_structured_test = {"description": "Direct JSON Desc", "amount": 789.01}
        apply_metadata_direct(
            client=mock_client, 
            selected_files_data=[mock_selected_files[0]], # Just one file
            metadata_results={}, 
            template_mappings={}, 
            default_template_id='enterprise_123_testTemplate',
            use_direct_json_input=True,
            direct_json_input=json.dumps(direct_json_structured_test)
        )


