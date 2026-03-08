import sys
import os

def generate_data(filename, size_in_mb):
    path = os.path.join("client/data", filename)
    
    print(f"Generating {size_in_mb} MB of fake data to {path}...")
    
    with open(path, "wb") as f:
        for _ in range(size_in_mb):
            f.write(os.urandom(1024 * 1024))
            
    print("Done!")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 generate_data.py <filename> <size_in_mb>")
        sys.exit(1)
        
    filename = sys.argv[1]
    try:
        size_in_mb = int(sys.argv[2])
    except ValueError:
        print("Size must be an integer.")
        sys.exit(1)
        
    generate_data(filename, size_in_mb)
