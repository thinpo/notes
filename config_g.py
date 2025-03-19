import csv
import yaml
from pathlib import Path
from typing import Dict, List, Any

def read_schema(schema_file: str) -> List[Dict[str, Any]]:
    """Read the schema CSV file and return a list of dictionaries."""
    with open(schema_file, 'r') as f:
        reader = csv.DictReader(f)
        return list(reader)

def generate_config(schema: List[Dict[str, Any]], asset_class: str) -> Dict[str, Any]:
    """Generate a YAML config for a specific asset class."""
    config = {
        'asset_class': asset_class,
        'xml_structure': {
            'root_element': 'Instruments',
            'record_element': 'Instrument',
            'fields': []
        },
        'csv_output': {
            'file_pattern': '{input_filename}_{asset_class}.csv',
            'field_order': []
        }
    }
    
    # Process fields for the asset class
    for row in schema:
        if row[asset_class] == '1':
            field = {
                'name': row['name'],
                'xpath': row['xpath'],
                'category': row['category'],
                'data_type': row['data_type'],
                'required': row['occurrence'] == '1'  # Required if occurrence is 1
            }
            
            # Add unbounded flag if occurrence is 'unbounded'
            if row['occurrence'] == 'unbounded':
                field['unbounded'] = True
            
            config['xml_structure']['fields'].append(field)
            config['csv_output']['field_order'].append(row['name'])
    
    return config

def save_yaml_config(config: Dict[str, Any], output_file: Path):
    """Save the config to a YAML file with proper formatting."""
    with open(output_file, 'w') as f:
        yaml.dump(config, f, sort_keys=False, default_flow_style=False, allow_unicode=True)

def main():
    # Create configs directory if it doesn't exist
    config_dir = Path('configs')
    config_dir.mkdir(exist_ok=True)
    
    # Read schema
    schema = read_schema('schema.csv')
    
    # Get asset classes from schema headers
    asset_classes = [col for col in schema[0].keys() 
                    if col not in ['xpath', 'name', 'category', 'occurrence', 'data_type']]
    
    # Generate configs for each asset class
    for asset_class in asset_classes:
        config = generate_config(schema, asset_class)
        
        # Save config to YAML file
        config_file = config_dir / f'{asset_class}_config.yaml'
        save_yaml_config(config, config_file)
        
        print(f"Generated YAML config for {asset_class}")

if __name__ == '__main__':
    main() 
