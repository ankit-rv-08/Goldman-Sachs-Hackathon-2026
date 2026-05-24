import sys
import json

class TypeNode:
    def __init__(self):
        self.primitive_types = set()
        self.children = {}       
        self.array_items = None  
        self.is_optional = False
        self.assigned_name = ""
        self.total_parent_objects_seen = 0  
        self.is_object = False  # Explicitly tracks if this node represents an object

def merge_node(node, data):
    # Base cases for primitives
    if data is None:
        node.primitive_types.add("null")
    elif isinstance(data, bool): # Note: bool must be checked before int in Python
        node.primitive_types.add("boolean")
    elif isinstance(data, (int, float)):
        node.primitive_types.add("number")
    elif isinstance(data, str):
        node.primitive_types.add("string")
        
    # Handle nested arrays
    elif isinstance(data, list):
        if node.array_items is None:
            node.array_items = TypeNode()
        for item in data:
            merge_node(node.array_items, item)
            
    # Handle objects
    elif isinstance(data, dict):
        node.is_object = True
        node.total_parent_objects_seen += 1
        
        # If we know a key but it's not in this dict, it must be optional
        for key, child_node in node.children.items():
            if key not in data:
                child_node.is_optional = True
                
        for key, val in data.items():
            if key not in node.children:
                node.children[key] = TypeNode()
                # If we've seen objects before this one, this new key was missing in them
                if node.total_parent_objects_seen > 1:
                    node.children[key].is_optional = True
            
            merge_node(node.children[key], val)

def assign_names(node, parent_key, seen_names):
    # 1. Pre-Order Assignment: Assign name to this object FIRST before recursing
    if node.is_object and not node.assigned_name:
        base_name = parent_key[0].upper() + parent_key[1:]
        
        if base_name not in seen_names:
            node.assigned_name = base_name
            seen_names.add(base_name)
        else:
            # Collision handling (start at 2)
            suffix = 2
            while f"{base_name}{suffix}" in seen_names:
                suffix += 1
            node.assigned_name = f"{base_name}{suffix}"
            seen_names.add(node.assigned_name)

    # 2. Recurse children depth-first, alphabetically
    for key in sorted(node.children.keys()):
        assign_names(node.children[key], key, seen_names)
        
    # 3. Recurse into arrays
    if node.array_items is not None:
        assign_names(node.array_items, parent_key, seen_names)

def get_type_string(node):
    components = list(node.primitive_types)
    
    if node.assigned_name:
        components.append(node.assigned_name)
        
    if node.array_items is not None:
        arr_inner = get_type_string(node.array_items)
        if arr_inner == "":
            components.append("unknown[]")
        elif " | " in arr_inner:
            components.append(f"({arr_inner})[]") 
        else:
            components.append(f"{arr_inner}[]")
            
    components.sort()
    return " | ".join(components)

def collect_interfaces(node, interfaces_dict):
    if node.assigned_name:
        props = []
        for key in sorted(node.children.keys()):
            child = node.children[key]
            opt_flag = "?" if child.is_optional else ""
            type_str = get_type_string(child)
            props.append(f"  {key}{opt_flag}: {type_str};")
            
        interfaces_dict[node.assigned_name] = props
        
    for child in node.children.values():
        collect_interfaces(child, interfaces_dict)
        
    if node.array_items is not None:
        collect_interfaces(node.array_items, interfaces_dict)

def solve(root_name, json_text):
    data = json.loads(json_text)
    root_node = TypeNode()
    root_node.is_object = True  # The root represents the top-level merged object
    
    # 1. Merge tree
    for item in data:
        merge_node(root_node, item)
        
    # 2. Resolve names
    seen_names = set([root_name])
    root_node.assigned_name = root_name 
    
    for key in sorted(root_node.children.keys()):
        assign_names(root_node.children[key], key, seen_names)
        
    if root_node.array_items is not None:
        assign_names(root_node.array_items, root_name, seen_names)
        
    # 3. Generate outputs
    interfaces_dict = {}
    collect_interfaces(root_node, interfaces_dict)
        
    output_blocks = []
    for name in sorted(interfaces_dict.keys()):
        props = interfaces_dict[name]
        if not props:
            output_blocks.append(f"export interface {name} {{}}")
        else:
            props_str = "\n".join(props)
            output_blocks.append(f"export interface {name} {{\n{props_str}\n}}")
            
    return "\n\n".join(output_blocks)

def main():
    lines = sys.stdin.read().split('\n')
    
    # Guard against trailing newlines causing errors
    if not lines or lines[0] == "":
        return
        
    t = int(lines[0])

    blocks = []
    for i in range(t):
        root_name = lines[1 + 2 * i].strip()
        json_text = lines[2 + 2 * i].strip()
        blocks.append(solve(root_name, json_text))

    sys.stdout.write('\n---\n'.join(blocks) + '\n')

if __name__ == '__main__':
    main()
