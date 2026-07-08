from pathlib import Path
from dotenv import load_dotenv
_backend_dir = Path(__file__).parent.parent
load_dotenv(_backend_dir / '.env')
