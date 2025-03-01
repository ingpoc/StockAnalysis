from pymongo import MongoClient
from datetime import datetime

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['stock_data']

# Get all existing holdings
holdings = list(db.holdings.find())
print(f"Found {len(holdings)} holdings to convert")

# Create a new collection for the converted holdings
if 'holdings_new' in db.list_collection_names():
    db.holdings_new.drop()

# Convert and insert each holding
for holding in holdings:
    # Map the fields from the existing schema to the new schema
    new_holding = {
        "symbol": holding.get('Instrument', ''),
        "company_name": holding.get('Instrument', ''),  # Using Instrument as company_name too
        "quantity": int(holding.get('Qty.', 0)),
        "average_price": float(holding.get('Avg. cost', 0)),
        "purchase_date": None,  # No purchase date in the original data
        "notes": None,  # No notes in the original data
        "timestamp": datetime.now()
    }
    
    # Insert the new holding
    db.holdings_new.insert_one(new_holding)

print(f"Converted {db.holdings_new.count_documents({})} holdings")

# Rename collections to replace the old one with the new one
db.holdings.rename('holdings_old')
db.holdings_new.rename('holdings')

print("Conversion complete. Old collection renamed to 'holdings_old'") 