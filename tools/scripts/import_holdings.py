import asyncio
import csv
import os
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from src.config import settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def import_holdings():
    logger.info(f"Connecting to MongoDB at {settings.MONGODB_URI}")
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            maxPoolSize=10,
            retryWrites=True
        )
        
        # Verify the connection
        await client.admin.command('ismaster')
        logger.info("Successfully connected to MongoDB")
        
        # Get database
        db = client[settings.MONGODB_DB_NAME]
        
        # Path to the CSV file
        csv_path = "../stockanalysisgui/docs/holdings.csv"
        
        if not os.path.exists(csv_path):
            logger.error(f"CSV file not found at {csv_path}")
            return
        
        logger.info(f"Reading holdings from {csv_path}")
        
        # Read CSV file and convert to holdings
        holdings_to_import = []
        with open(csv_path, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Skip empty rows
                if not row.get('Instrument'):
                    continue
                
                # Extract data from CSV
                symbol = row['Instrument'].strip()
                quantity = float(row['Qty.'].replace(',', '')) if row['Qty.'] else 0
                avg_price = float(row['Avg. cost'].replace(',', '')) if row['Avg. cost'] else 0
                
                # Create holding document
                holding = {
                    "symbol": symbol,
                    "company_name": symbol,  # Using symbol as company name since it's not in CSV
                    "quantity": int(quantity),
                    "average_price": avg_price,
                    "purchase_date": datetime.now().isoformat(),
                    "notes": f"Imported from CSV on {datetime.now().strftime('%Y-%m-%d')}",
                    "timestamp": datetime.now().isoformat()
                }
                holdings_to_import.append(holding)
        
        if not holdings_to_import:
            logger.warning("No holdings found in CSV to import")
            return
        
        logger.info(f"Found {len(holdings_to_import)} holdings to import")
        
        # Clear existing holdings
        await db.holdings.delete_many({})
        logger.info("Cleared existing holdings")
        
        # Insert new holdings
        result = await db.holdings.insert_many(holdings_to_import)
        logger.info(f"Successfully imported {len(result.inserted_ids)} holdings")
        
        # Display some examples
        logger.info("Examples of imported holdings:")
        async for holding in db.holdings.find().limit(5):
            logger.info(f"  - {holding['symbol']}: {holding['quantity']} shares at {holding['average_price']}")
        
    except Exception as e:
        logger.error(f"Error importing holdings: {e}")
    finally:
        # Close the connection
        if 'client' in locals():
            client.close()
            logger.info("MongoDB connection closed")

if __name__ == "__main__":
    asyncio.run(import_holdings()) 