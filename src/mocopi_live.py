import json
import time
from pythonosc import dispatcher
from pythonosc import osc_server
from pythonosc import udp_client

# --- CONFIGURATION ---
IP_LISTEN = "0.0.0.0"   # Listen to Mocopi
PORT_LISTEN = 39539     # Port defined in Mocopi App

IP_SEND = "127.0.0.1"   # Unity IP (Localhost)
PORT_SEND = 39540       # Port Unity listens to

# Create the client to send data to Unity
unity_client = udp_client.SimpleUDPClient(IP_SEND, PORT_SEND)

def data_handler(address, *args):
    """
    1. Receive data from Mocopi.
    2. PROCESS: Convert to JSON object.
    3. RELAY: Forward raw data to Unity immediately.
    """
    
    # --- A. CONVERT TO JSON ---
    # Create a Python dictionary first
    data_dict = {
        "timestamp": time.time(),
        "bone": args[0],
        "position": {
            "x": args[1], 
            "y": args[2], 
            "z": args[3]
        },
        "rotation": {
            "x": args[4], 
            "y": args[5], 
            "z": args[6], 
            "w": args[7]
        }
    }
    
    # Convert dictionary to JSON string
    json_data = json.dumps(data_dict)

    # --- B. USE THE JSON ---
    # Example: Print JSON for "Head" only to avoid console spam
    if args[0] == "Head":
         print(f"JSON Output: {json_data}")
         
    # You can now use 'json_data' to send to a Websocket, save to DB, etc.

    # --- C. FORWARD TO UNITY ---
    # We send the original raw address and arguments to Unity
    try:
        unity_client.send_message(address, args)
    except Exception as e:
        print(f"Error forwarding to Unity: {e}")

if __name__ == "__main__":
    disp = dispatcher.Dispatcher()
    
    # Map all VMC bone data
    disp.map("/VMC/Ext/Bone/Pos", data_handler)

    print(f"=== JSON RELAY STARTED ===")
    print(f"1. Listening to Mocopi on port {PORT_LISTEN}")
    print(f"2. Converting to JSON (See console)")
    print(f"3. Forwarding to Unity on port {PORT_SEND}")
    
    try:
        server = osc_server.ThreadingOSCUDPServer((IP_LISTEN, PORT_LISTEN), disp)
        server.serve_forever()
    except OSError:
        print(f"Error: Port {PORT_LISTEN} is occupied. Close other apps.")