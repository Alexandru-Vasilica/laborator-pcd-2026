import subprocess
import os
import time


PROTOCOLS = ["tcp", "udp", "udp-stop-and-wait", "quic", "quic-stop-and-wait"]
QUIC_BLOCK_SIZES = [512, 1024]
BLOCK_SIZES =[512,1024, 16384, 60000]
FILES = {
    "medium": "client/data/medium",
    "large": "client/data/large"
}
BINARY_PATH = "target/release/client"

def run_experiment(protocol, block_size, file_path):
    print(f"\n--- Experiment: {protocol} | Block: {block_size} | File: {file_path} ---")
    
    cmd = [
        BINARY_PATH,
        "--transport", protocol,
        "--block-size", str(block_size),
        "--file-path", file_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print(result.stdout.strip())
        else:
            print(f"Error: {result.stderr.strip()}")
            
    except subprocess.TimeoutExpired:
        print("Experiment timed out.")
    except Exception as e:
        print(f"Unexpected error: {e}")

def main():
    for label, path in FILES.items():
        if not os.path.exists(path):
            print(f"Warning: {label} file at {path} not found")
            return

    if not os.path.exists(BINARY_PATH):
        print(f"Error: Binary {BINARY_PATH} not found. Run 'cargo build' first.")
        return

    print("Starting experiments. Ensure the server is running in another terminal.")
    
    for label, path in FILES.items():
        for protocol in PROTOCOLS:
            block_sizes = BLOCK_SIZES if protocol not in ["quic", "quic-stop-and-wait"] else QUIC_BLOCK_SIZES
            for block_size in block_sizes:
                run_experiment(protocol, block_size, path)
                time.sleep(0.5)

if __name__ == "__main__":
    main()
