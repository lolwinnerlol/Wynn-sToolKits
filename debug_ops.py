
import bpy
import os

output_path = os.path.join(os.path.dirname(__file__), "ops_list.txt")

try:
    with open(output_path, "w") as f:
        if hasattr(bpy.ops, "extensions"):
            for op in dir(bpy.ops.extensions):
                f.write(op + "\n")
        else:
            f.write("No 'extensions' module in bpy.ops\n")
            
        # Also check bpy.ops.preferences if related
        f.write("\n--- PREFERENCES ---\n")
        if hasattr(bpy.ops, "preferences"):
            for op in dir(bpy.ops.preferences):
                if "ext" in op or "addon" in op:
                    f.write(op + "\n")

except Exception as e:
    print(e)
