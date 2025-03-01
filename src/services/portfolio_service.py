from src.utils.database import get_database
from src.models.schemas import Holding, HoldingsList
from typing import List, Optional
import csv
import io
from datetime import datetime
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

class PortfolioService:
    def __init__(self):
        self.collection_name = "holdings"

    async def get_holdings(self) -> List[Holding]:
        """Get all holdings from the database"""
        db = await get_database()
        holdings = []
        
        try:
            cursor = db[self.collection_name].find()
            async for document in cursor:
                try:
                    # Ensure _id is properly handled
                    if "_id" in document and not isinstance(document["_id"], str):
                        # This will be converted by the Holding model's PyObjectId
                        pass
                    holdings.append(Holding(**document))
                except Exception as e:
                    logger.error(f"Error parsing holding document: {e}, document: {document}")
            return holdings
        except Exception as e:
            logger.error(f"Error fetching holdings: {e}")
            raise

    async def add_holding(self, holding: Holding) -> Holding:
        """Add a new holding to the database"""
        db = await get_database()
        
        try:
            result = await db[self.collection_name].insert_one(holding.model_dump(exclude={"id"}, by_alias=True))
            holding.id = result.inserted_id
            return holding
        except Exception as e:
            logger.error(f"Error adding holding: {e}")
            raise

    async def update_holding(self, holding_id: str, holding: Holding) -> Optional[Holding]:
        """Update an existing holding"""
        db = await get_database()
        
        try:
            result = await db[self.collection_name].update_one(
                {"_id": ObjectId(holding_id)},
                {"$set": holding.model_dump(exclude={"id"}, by_alias=True)}
            )
            
            if result.modified_count:
                return holding
            return None
        except Exception as e:
            logger.error(f"Error updating holding: {e}")
            raise

    async def delete_holding(self, holding_id: str) -> bool:
        """Delete a holding from the database"""
        db = await get_database()
        
        try:
            result = await db[self.collection_name].delete_one({"_id": ObjectId(holding_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting holding: {e}")
            raise

    async def clear_holdings(self) -> int:
        """Clear all holdings from the database"""
        db = await get_database()
        
        try:
            result = await db[self.collection_name].delete_many({})
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error clearing holdings: {e}")
            raise

    async def import_holdings_from_csv(self, csv_content: str) -> List[Holding]:
        """Import holdings from CSV content"""
        db = await get_database()
        holdings = []
        
        try:
            # First clear existing holdings
            await self.clear_holdings()
            
            # Parse CSV content
            csv_file = io.StringIO(csv_content)
            csv_reader = csv.DictReader(csv_file)
            
            for row in csv_reader:
                # Convert row data to Holding model
                holding = Holding(
                    symbol=row.get('symbol', '').strip(),
                    company_name=row.get('company_name', '').strip(),
                    quantity=int(row.get('quantity', 0)),
                    average_price=float(row.get('average_price', 0)),
                    purchase_date=datetime.fromisoformat(row.get('purchase_date')) if row.get('purchase_date') else None,
                    notes=row.get('notes', '')
                )
                
                # Insert into database
                result = await db[self.collection_name].insert_one(
                    holding.model_dump(exclude={"id"}, by_alias=True)
                )
                holding.id = result.inserted_id
                holdings.append(holding)
                
            return holdings
        except Exception as e:
            logger.error(f"Error importing holdings from CSV: {e}")
            raise 