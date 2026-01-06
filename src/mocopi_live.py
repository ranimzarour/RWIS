from pythonosc import dispatcher
from pythonosc import osc_server

# --- CONFIGURATION ---
# "0.0.0.0" allows the server to listen on all available network interfaces (WiFi, Ethernet)
IP = "0.0.0.0" 
# The port must match the one configured in the Mocopi App (usually 39539 or 39540)
PORT = 39539    

def data_handler(address, *args):
    """
    Callback function triggered automatically for every received message.
    
    The 'args' tuple contains the VMC protocol data in this order:
    0: Bone Name (string)
    1-3: Position X, Y, Z (float)
    4-7: Rotation Quaternion X, Y, Z, W (float)
    """
    
    # 1. Get the name of the bone (e.g., "Head", "Hips", "RightHand")
    bone_name = args[0]
    
    # 2. FILTERING
    # To avoid flooding the console, we only print data for the "Head".
    # Remove this 'if' statement to see data for all bones.
    if bone_name == "Head":
        
        # Extract Position (in meters)
        pos_x, pos_y, pos_z = args[1], args[2], args[3]
        
        # Extract Rotation (Quaternion format)
        rot_x, rot_y, rot_z, rot_w = args[4], args[5], args[6], args[7]
        
        # Print the data
        print(f"--- {bone_name} ---")
        print(f"Position : X={pos_x:.2f}, Y={pos_y:.2f}, Z={pos_z:.2f}")
        print(f"Rotation : Quat({rot_x:.2f}, {rot_y:.2f}, {rot_z:.2f}, {rot_w:.2f})")
        print("-" * 20)

if __name__ == "__main__":
    # Initialize the dispatcher to handle incoming OSC messages
    disp = dispatcher.Dispatcher()
    
    # Map the standard VMC address "/VMC/Ext/Bone/Pos" to our data_handler function
    disp.map("/VMC/Ext/Bone/Pos", data_handler)

    print(f"=== Server listening on {IP}:{PORT} ===")
    print("Waiting for Mocopi data via UDP...")
    print("Press Ctrl+C to stop.")

    try:
        # Create the UDP server (ThreadingOSCUDPServer handles requests in separate threads)
        server = osc_server.ThreadingOSCUDPServer((IP, PORT), disp)
        server.serve_forever()
        
    except OSError as e:
        print(f"Error: Port {PORT} might be in use or blocked by firewall.")
        print(f"Details: {e}")
    except KeyboardInterrupt:
        print("\nServer stopped by user.")