import bpy
import os
import shutil
import re
import zipfile
import tempfile

# Configuration: Path to the master addon folder on the shared drive
MASTER_PATH = r"X:\My Drive\80_Resources\Blender Addons"

def get_addon_path():
    """Gets the root path of the Wynn's Toolkits addon."""
    return os.path.dirname(os.path.realpath(__file__))

def parse_version(file_path):
    """Extracts version tuple from bl_info in __init__.py"""
    if not os.path.exists(file_path):
        return (0, 0, 0)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Look for "version": (1, 2, 3) pattern
        match = re.search(r'"version":\s*\((.*?)\)', content)
        if match:
            version_str = match.group(1)
            return tuple(map(int, re.findall(r'\d+', version_str)))
    except:
        pass
    return (0, 0, 0)

def get_latest_zip_info():
    """Finds the zip file with the highest version number in MASTER_PATH"""
    if not os.path.exists(MASTER_PATH):
        print(f"Updater Error: Master path not found: {MASTER_PATH}")
        return None, (0,0,0)
    
    files = os.listdir(MASTER_PATH)
    # Regex to match Wynn-sToolKits-main1.1.zip or similar
    pattern = re.compile(r"Wynn-sToolKits-main[-_]?(\d+(?:\.\d+)*)\.zip", re.IGNORECASE)
    
    versions = []
    for f in files:
        match = pattern.match(f)
        if match:
            ver_str = match.group(1)
            try:
                ver_tuple = tuple(map(int, ver_str.split('.')))
                versions.append((ver_tuple, f))
            except ValueError:
                continue
            
    if not versions:
        return None, (0,0,0)
        
    # Sort by version tuple descending
    versions.sort(key=lambda x: x[0], reverse=True)
    return versions[0] # Returns ((1, 1), 'filename.zip')

def check_updates_core():
    """Compares local version with master zip version"""
    # Get the path to the main __init__.py for this addon
    local_path = os.path.join(get_addon_path(), "__init__.py")
    
    local_ver = parse_version(local_path)
    master_ver_tuple, master_filename = get_latest_zip_info()
    
    if master_filename is None:
        return False, local_ver, (0,0,0)
    
    return master_ver_tuple > local_ver, local_ver, master_ver_tuple

class WM_OT_check_for_updates(bpy.types.Operator):
    """Check for addon updates from the shared drive"""
    bl_idname = "wm.check_for_updates"
    bl_label = "Check for Updates"
    
    def execute(self, context):
        is_available, local, master = check_updates_core()
        context.window_manager.wynn_update_available = is_available
        
        if is_available:
            self.report({'INFO'}, f"Update Available: {master} (Current: {local})")
            bpy.ops.wm.update_addon('INVOKE_DEFAULT')
        elif master == (0, 0, 0):
            self.report({'WARNING'}, f"No valid zip files found in: {MASTER_PATH}")
        else:
            self.report({'INFO'}, f"Addon is up to date: {local}")
            
        return {'FINISHED'}

class WM_OT_update_addon(bpy.types.Operator):
    """Update the addon from the shared drive and restart Blender"""
    bl_idname = "wm.update_addon"
    bl_label = "Update Addon"
    bl_description = "Update from Master Drive. Please save your work first!"
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        ver_info, _ = get_latest_zip_info()
        ver_str = str(ver_info) if ver_info else "Unknown"
        layout.label(text=f"New Version Available: {ver_str}", icon='INFO')
        layout.label(text="Click OK to download and restart Blender.")
        layout.separator()
        layout.label(text="PLEASE SAVE YOUR WORK FIRST!", icon='ERROR')

    def execute(self, context):
        local_dir = get_addon_path()
        
        master_ver_tuple, zip_filename = get_latest_zip_info()
        if not zip_filename:
            self.report({'ERROR'}, f"No update zip found in: {MASTER_PATH}")
            return {'CANCELLED'}
            
        zip_path = os.path.join(MASTER_PATH, zip_filename)
        # Define backup path
        backup_dir = local_dir + "_BACKUP"
        
        # Logic: 
        # 1. Extract new version to temp (Validate)
        # 2. Rename current version to BACKUP
        # 3. Copy temp to current location
        # 4. If success, try delete BACKUP
        # 5. If fail, delete partial current, restore BACKUP
        
        try:
            # 1. Prepare Update in Temp
            with tempfile.TemporaryDirectory() as temp_dir:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # Loose Validation: Look for the folder containing __init__.py
                # This relaxes the restriction on 'Animate'/'Rig' folders
                source_path = None
                for root, dirs, files in os.walk(temp_dir):
                    if "__init__.py" in files:
                        source_path = root
                        break
                
                if not source_path:
                    self.report({'ERROR'}, "Invalid Zip: Could not find '__init__.py'.")
                    return {'CANCELLED'}

                # Remove old backup if it lingers from a previous crash
                if os.path.exists(backup_dir):
                    try:
                        shutil.rmtree(backup_dir)
                    except OSError:
                        self.report({'ERROR'}, "Cannot remove old backup folder. Please check permissions or delete manually: " + backup_dir)
                        return {'CANCELLED'}

                # 2. Rename Local to Backup
                # Windows usually allows renaming a folder even if files inside are in use
                try:
                    os.rename(local_dir, backup_dir)
                except OSError as e:
                    self.report({'ERROR'}, f"Cannot backup current version (File in use?): {e}")
                    return {'CANCELLED'}

                # 3. Copy New Version to Local
                try:
                    # ignore pycache during copy to be clean
                    shutil.copytree(source_path, local_dir, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
                except Exception as e:
                    # Update failed! Try to restore backup
                    self.report({'ERROR'}, f"Copying new files failed: {e}. Restoring backup...")
                    
                    # Clean up the possibly corrupted new folder
                    if os.path.exists(local_dir):
                        shutil.rmtree(local_dir)
                    
                    # Restore backup
                    try:
                        os.rename(backup_dir, local_dir)
                        self.report({'INFO'}, "Backup restored successfully.")
                    except OSError as e2:
                        self.report({'ERROR'}, f"CRITICAL: Could not restore backup! Manual repair needed. Error: {e2}")
                    
                    return {'CANCELLED'}
            
            # 4. Clean up Backup
            # On Windows, we might not be able to delete the backup if this script (updater.py) 
            # is running from within the renamed folder.
            try:
                shutil.rmtree(backup_dir)
            except OSError:
                self.report({'WARNING'}, "Update successful, but could not delete backup folder (files in use). Please delete it manually if desired.")
                
            self.report({'INFO'}, "Update Successful! Please Restart Blender.")
            
        except Exception as e:
            self.report({'ERROR'}, f"Unexpected Error: {e}")
            return {'CANCELLED'}
            
        return {'FINISHED'}
