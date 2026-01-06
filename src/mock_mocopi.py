import socket
import time
import random

def run_mock_sender(target_ip="127.0.0.1", target_port=12351):
    """
    Simulates the Mocopi app by sending fake UDP packets to a local listener.
    
    Args:
        target_ip (str): The IP to send data to ("127.0.0.1" for localhost).
        target_port (int): The port the listener is expecting (default 12351).
    """
    print(f"--- Starting Mock Mocopi Sender targeting {target_ip}:{target_port} ---")
    
    # Create a UDP socket for sending
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    try:
        while True:
            # Generate fake data (e.g., 50 bytes of random values to mimic a binary packet)
            # In a real scenario, this would be the bone structure data.
            fake_payload = bytes([random.getrandbits(8) for _ in range(50)])
            
            # Send the packet
            sock.sendto(fake_payload, (target_ip, target_port))
            
            print(f"Sent fake packet of {len(fake_payload)} bytes")
            
            # Mocopi usually sends data at 50Hz or 60Hz (approx every 0.02 seconds)
            time.sleep(0.02)
            
    except KeyboardInterrupt:
        print("\nStopping simulation...")
    finally:
        sock.close()

if __name__ == "__main__":
    # Ensure this port matches your listener script
    run_mock_sender()