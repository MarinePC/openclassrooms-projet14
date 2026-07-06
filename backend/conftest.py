# conftest.py — configuration pytest
import sys
import os

# Ajoute src/ au path pour que pytest trouve les modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))