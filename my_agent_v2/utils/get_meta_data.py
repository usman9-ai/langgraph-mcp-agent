import json

# read metadata from a json file
def get_datasource_metadata() -> dict:
    with open("C:\\Langgraph Agent\\my_agent\\utils\\metadata.json", "r") as f:
        metadata = json.load(f)
    return metadata

metadata = get_datasource_metadata()

list_of_unique_data_types = []
for field in metadata.get("fields", []):
    print(field)
    if field.get("name") == "Transaction Count":
        print("Found Transaction Count field:", field)
        
    data_type = field.get("dataType")
    if data_type and data_type not in list_of_unique_data_types:
        list_of_unique_data_types.append(data_type)

print("List of unique data types:", list_of_unique_data_types)