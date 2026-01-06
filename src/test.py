from pythonosc import dispatcher
from pythonosc import osc_server

# --- CONFIGURATION ---
IP = "0.0.0.0"   
PORT = 12352     # Vérifiez que c'est le même port que dans l'App

def print_everything(address, *args):
    """
    Cette fonction s'active pour N'IMPORTE QUEL message reçu.
    """
    print(f"J'AI REÇU QUELQUE CHOSE !")
    print(f"Adresse : {address}")
    print(f"Contenu : {args}")
    print("-" * 20)

if __name__ == "__main__":
    disp = dispatcher.Dispatcher()
    
    # L'étoile "*" signifie : Capture TOUS les messages, peu importe le nom
    disp.map("*", print_everything)

    print(f"=== MODE DIAGNOSTIC ===")
    print(f"J'écoute sur le port {PORT}")
    print("En attente de n'importe quel signal...")
    
    try:
        server = osc_server.ThreadingOSCUDPServer((IP, PORT), disp)
        server.serve_forever()
    except OSError:
        print(f"ERREUR : Le port {PORT} est déjà pris ! Fermez les autres scripts Python ou Unity.")