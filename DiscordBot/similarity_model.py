from sentence_transformers import SentenceTransformer

# set up sentence transformer for similarity detection
SENTENCE_MODEL = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2') # 90M