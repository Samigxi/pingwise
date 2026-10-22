#!/usr/bin/env python3
"""
Pingwise — Peer-to-Peer Distributed Hash Table (DHT) Simulator
Entry point: starts Flask server on localhost:5000
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import app

if __name__ == '__main__':
    banner = """
    =======================================================
     ____  ___ _   _  ______        _____ ____  _____ 
    |  _ \\|_ _| \\ | |/ ___\\ \\      / /_ _/ ___|| ____|
    | |_) || ||  \\| | |  _ \\ \\ /\\ / / | |\\___ \\|  _|  
    |  __/ | || |\\  | |_| | \\ V  V /  | | ___) | |___ 
    |_|   |___|_| \\_|\\____|  \\_/\\_/  |___|____/|_____|
                                                      
     Kademlia P2P Distributed Hash Table (DHT) Simulator
     Serving at: http://localhost:5000
    =======================================================
    """
    print(banner)
    app.run(host='0.0.0.0', port=5000, debug=True)
