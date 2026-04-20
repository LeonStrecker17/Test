ingestion.py


import os
from pathlib import Path
from backend.core.pipelines import create_indexing_pipeline

def run():
    pipe = create_indexing_pipeline()
    data_path = Path("./data")
    files = [data_path / f for f in os.listdir(data_path) if f.endswith(".pdf")]
    
    print(f"Indexing {len(files)} files...")
    pipe.run({"converter": {"sources": files}})
    print("Done!")

if __name__ == "__main__":
    run()
  
