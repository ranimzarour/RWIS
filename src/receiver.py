import socket
import struct

def start_mocopi_listener(listen_ip="0.0.0.0", listen_port=12351):
    """
    Starts a UDP server to listen for Mocopi data packets.
    
    Args:
        listen_ip (str): IP address to bind (0.0.0.0 listens on all interfaces).
        listen_port (int): The port defined in the Mocopi app settings.
    """
    print(f"--- Starting Mocopi Listener on {listen_ip}:{listen_port} ---")
    
    # Create a UDP socket
    try:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind((listen_ip, listen_port))
        
        print("Waiting for data stream...")
        
        while True:
            # Receive data (buffer size 1024 is usually sufficient for headers)
            data, source_address = udp_socket.recvfrom(2048)
            
            # Process the raw binary data
            process_packet(data, source_address)
            
    except KeyboardInterrupt:
        print("\nStopping listener...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        udp_socket.close()

def process_packet(raw_data, source_address):
    """
    Handles the incoming raw byte data.
    """
    # Mocopi sends binary data. For now, we print the length and source.
    data_length = len(raw_data)
    
    # Example: Attempting to decode the first few bytes to check format
    # This depends on whether you selected generic UDP or VMC/OSC in the app.
    print(f"Received {data_length} bytes from {source_address}")
    
    # Optional: Print raw hex to analyze structure
    # print(raw_data.hex())

if __name__ == "__main__":
    # Ensure this port matches the one in your Mocopi App
    PORT_TO_LISTEN = 12351 
    
    start_mocopi_listener(listen_port=PORT_TO_LISTEN)