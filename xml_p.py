import xml.etree.ElementTree as ET
import csv
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class XMLParser:
    def __init__(self, config_file: str):
        """Initialize the parser with a YAML config file."""
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)
        self.asset_class = self.config['asset_class']
        self.xml_structure = self.config['xml_structure']
        self.csv_output = self.config['csv_output']
        self.fields = self.xml_structure['fields']

    def _split_xpath(self, xpath: str) -> Tuple[str, Optional[str]]:
        """Split xpath into element path and attribute name."""
        if '@' in xpath:
            # Handle attribute selectors in the path (e.g., //path/to[@attr='value'])
            if '[' in xpath and ']' in xpath:
                path = xpath
                attr = None
            else:
                path, attr = xpath.rsplit('@', 1)
                # Remove trailing slash if present
                path = path.rstrip('/')
            return path, attr
        return xpath, None

    def _get_element_value(self, element: ET.Element, xpath: str) -> Any:
        """Get the value of an element or attribute based on xpath."""
        path, attr = self._split_xpath(xpath)
        
        if not path:
            # Handle root-level attributes
            return element.get(attr) if attr else element.text
            
        try:
            # Convert absolute path to relative
            if path.startswith('//'):
                path = path.split('/', 3)[-1]
            
            # Find the element
            target = element.find(path)
            if target is None:
                return None
                
            # Return attribute value or element text
            return target.get(attr) if attr else target.text
        except Exception as e:
            logger.error(f"Error getting value for xpath {xpath}: {str(e)}")
            return None

    def _convert_value(self, value: str, data_type: str) -> Any:
        """Convert string value to appropriate data type."""
        if value is None:
            return None
            
        if data_type == 'decimal':
            return float(value) if value else None
        elif data_type == 'boolean':
            return value.lower() == 'true'
        elif data_type == 'date':
            try:
                return datetime.strptime(value, '%Y-%m-%d').strftime('%Y-%m-%d')
            except ValueError:
                return value
        elif data_type == 'integer':
            return int(value) if value else None
        else:
            return value

    def _handle_unbounded_fields(self, record: ET.Element, field: Dict[str, Any]) -> List[Any]:
        """Handle fields that can occur multiple times (unbounded)."""
        xpath = field['xpath']
        data_type = field['data_type']
        
        try:
            # Convert absolute path to relative
            if xpath.startswith('//'):
                xpath = xpath.split('/', 3)[-1]
            
            # Handle attribute selectors in the path
            if '[' in xpath and ']' in xpath:
                elements = record.findall(xpath)
                if '@' in xpath:
                    # Extract values from matching elements
                    return [self._convert_value(elem.text, data_type) 
                           for elem in elements if elem is not None]
                else:
                    # Extract text from matching elements
                    return [self._convert_value(elem.text, data_type) 
                           for elem in elements if elem is not None]
            else:
                # Handle regular paths with attributes
                path, attr = self._split_xpath(xpath)
                if attr:
                    elements = record.findall(path) if path else [record]
                    return [self._convert_value(elem.get(attr), data_type) 
                           for elem in elements if elem is not None]
                else:
                    elements = record.findall(path)
                    return [self._convert_value(elem.text, data_type) 
                           for elem in elements if elem is not None]
        except Exception as e:
            logger.error(f"Error handling unbounded field {xpath}: {str(e)}")
            return []

    def _validate_required_fields(self, record: Dict[str, Any], field: Dict[str, Any]) -> bool:
        """Validate that required fields are present and not None."""
        if field.get('required', False):
            value = record.get(field['name'])
            if value is None:
                logger.warning(f"Required field {field['name']} is missing or None")
                return False
        return True

    def parse_xml(self, xml_file: str) -> List[Dict[str, Any]]:
        """Parse an XML file and return a list of dictionaries containing the extracted data."""
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        # Find all record elements using the configured record element name
        records = root.findall(f'.//{self.xml_structure["record_element"]}')
        results = []
        
        for record in records:
            record_data = {}
            is_valid = True
            
            for field in self.fields:
                xpath = field['xpath']
                name = field['name']
                
                # Handle unbounded fields
                if field.get('unbounded', False):
                    values = self._handle_unbounded_fields(record, field)
                    record_data[name] = values
                else:
                    # Handle single occurrence fields
                    value = self._get_element_value(record, xpath)
                    record_data[name] = self._convert_value(value, field['data_type'])
                
                # Validate required fields
                if not self._validate_required_fields(record_data, field):
                    is_valid = False
            
            if is_valid:
                results.append(record_data)
            else:
                logger.warning(f"Skipping invalid record due to missing required fields")
        
        return results

    def save_to_csv(self, data: List[Dict[str, Any]], output_file: str):
        """Save the parsed data to a CSV file."""
        if not data:
            logger.warning(f"No data to write to {output_file}")
            return
            
        fieldnames = self.csv_output['field_order']
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            # Handle unbounded fields by creating multiple rows if needed
            for record in data:
                # Find the maximum length of any unbounded field
                max_length = max(
                    (len(v) for v in record.values() if isinstance(v, list)),
                    default=0
                )
                
                # Create multiple rows if there are unbounded fields
                if max_length > 0:
                    for i in range(max_length):
                        row = {}
                        for field in fieldnames:
                            value = record[field]
                            if isinstance(value, list):
                                row[field] = value[i] if i < len(value) else None
                            else:
                                row[field] = value
                        writer.writerow(row)
                else:
                    writer.writerow(record)
        
        logger.info(f"Successfully wrote {len(data)} records to {output_file}")

def process_xml_files(input_dir: str, config_dir: str, output_dir: str):
    """Process all XML files in the input directory using configs from config_dir."""
    input_path = Path(input_dir)
    config_path = Path(config_dir)
    output_path = Path(output_dir)
    
    # Create output directory if it doesn't exist
    output_path.mkdir(exist_ok=True)
    
    # Process each XML file
    for xml_file in input_path.glob('*.xml'):
        logger.info(f"Processing {xml_file}")
        
        # Try to determine asset class from filename
        asset_class = None
        for config_file in config_path.glob('*_config.yaml'):
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
                if config['asset_class'] in xml_file.stem:
                    asset_class = config['asset_class']
                    break
        
        if not asset_class:
            logger.error(f"Could not determine asset class for {xml_file}")
            continue
            
        config_file = config_path / f'{asset_class}_config.yaml'
        if not config_file.exists():
            logger.error(f"Config file not found for {asset_class}")
            continue
            
        parser = XMLParser(str(config_file))
        data = parser.parse_xml(str(xml_file))
        
        # Use the file pattern from config
        output_file = output_path / parser.csv_output['file_pattern'].format(
            input_filename=xml_file.stem,
            asset_class=asset_class
        )
        parser.save_to_csv(data, str(output_file))

def main():
    # Example usage
    input_dir = 'input_xml'
    config_dir = 'configs'
    output_dir = 'output_csv'
    
    process_xml_files(input_dir, config_dir, output_dir)

if __name__ == '__main__':
    main() 
