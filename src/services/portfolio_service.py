from src.utils.database import get_database
from src.models.schemas import Holding, HoldingsList, EnrichedHolding
from typing import List, Optional, Dict
import csv
import io
from datetime import datetime
from bson import ObjectId
import logging
from src.services.market_service import MarketService

logger = logging.getLogger(__name__)

class PortfolioService:
    def __init__(self):
        self.collection_name = "holdings"
        self.market_service = MarketService()

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
                # Skip empty rows
                if not row.get('Instrument'):
                    continue
                    
                # Convert row data to Holding model
                try:
                    symbol = row.get('Instrument', '').strip().replace('"', '')
                    quantity = int(float(row.get('Qty.', 0)))
                    avg_price = float(row.get('Avg. cost', 0))
                    
                    # Create holding with available data
                    holding = Holding(
                        symbol=symbol,
                        company_name=symbol,  # Use symbol as company name if not available
                        quantity=quantity,
                        average_price=avg_price,
                        notes=f"Imported from CSV on {datetime.now().strftime('%Y-%m-%d')}"
                    )
                    
                    # Insert into database
                    result = await db[self.collection_name].insert_one(
                        holding.model_dump(exclude={"id"}, by_alias=True)
                    )
                    holding.id = result.inserted_id
                    holdings.append(holding)
                except Exception as e:
                    logger.error(f"Error processing row {row}: {e}")
                    continue
                
            return holdings
        except Exception as e:
            logger.error(f"Error importing holdings from CSV: {e}")
            raise

    async def get_enriched_holdings(self) -> List[EnrichedHolding]:
        """Get all holdings enriched with current price information"""
        db = await get_database()
        holdings = []
        
        try:
            # Get basic holdings first
            cursor = db[self.collection_name].find()
            basic_holdings = []
            async for document in cursor:
                try:
                    if "_id" in document and not isinstance(document["_id"], str):
                        pass
                    basic_holdings.append(Holding(**document))
                except Exception as e:
                    logger.error(f"Error parsing holding document: {e}, document: {document}")
            
            # If no holdings, return empty list
            if not basic_holdings:
                return []
                
            # Process each holding to fetch current price
            for holding in basic_holdings:
                try:
                    # Try to fetch stock details
                    stock_details = await self.market_service.get_stock_details(holding.symbol)
                    
                    # Get current price from stock details
                    if stock_details and stock_details.formatted_metrics and stock_details.formatted_metrics.get("cmp"):
                        cmp_value = stock_details.formatted_metrics.get("cmp", "0")
                        # Clean up the price by removing currency symbols
                        clean_price = cmp_value.replace("₹", "").replace("$", "").replace(",", "").strip()
                        current_price = float(clean_price)
                        
                        # Calculate values
                        current_value = current_price * holding.quantity
                        investment_value = holding.average_price * holding.quantity
                        gain_loss = current_value - investment_value
                        gain_loss_percentage = (gain_loss / investment_value) * 100 if investment_value > 0 else 0
                        
                        # Create enriched holding
                        enriched_holding = EnrichedHolding(
                            **holding.model_dump(),
                            current_price=current_price,
                            current_value=current_value,
                            gain_loss=gain_loss,
                            gain_loss_percentage=gain_loss_percentage,
                            has_error=False
                        )
                        holdings.append(enriched_holding)
                    else:
                        # No price data, create fallback holding
                        fallback_holding = self._create_fallback_holding(
                            holding,
                            "Could not retrieve current price data"
                        )
                        holdings.append(fallback_holding)
                        
                except Exception as e:
                    logger.warning(f"Error enriching holding for {holding.symbol}: {str(e)}")
                    # Create fallback holding with error
                    fallback_holding = self._create_fallback_holding(
                        holding,
                        f"Error getting price data: {str(e)}"
                    )
                    holdings.append(fallback_holding)
            
            return holdings
            
        except Exception as e:
            logger.error(f"Error fetching enriched holdings: {e}")
            raise

    async def get_batch_enriched_holdings(self) -> List[EnrichedHolding]:
        """Get all holdings enriched with current price information using batch API for efficiency"""
        db = await get_database()
        
        try:
            # Get basic holdings first
            cursor = db[self.collection_name].find()
            basic_holdings = []
            async for document in cursor:
                try:
                    if "_id" in document and not isinstance(document["_id"], str):
                        pass
                    basic_holdings.append(Holding(**document))
                except Exception as e:
                    logger.error(f"Error parsing holding document: {e}, document: {document}")
            
            # If no holdings, return empty list
            if not basic_holdings:
                return []
                
            # Extract unique symbols to fetch
            unique_symbols = list(set(holding.symbol for holding in basic_holdings))
            
            if not unique_symbols:
                return []
                
            logger.info(f"Fetching batch stock details for {len(unique_symbols)} symbols")
            
            # Get all stock details in one batch call
            batch_result = {}
            try:
                batch_result = await self.market_service.get_batch_stock_details(unique_symbols)
            except Exception as e:
                logger.error(f"Error fetching batch stock details: {e}")
                # Continue with empty results and fallbacks
                
            # Map holdings to enriched holdings
            enriched_holdings = []
            for holding in basic_holdings:
                try:
                    # Check if we have stock details for this symbol
                    stock_details = batch_result.get(holding.symbol)
                    
                    if stock_details and not isinstance(stock_details, dict):
                        # Get current price if available
                        if hasattr(stock_details, 'formatted_metrics') and stock_details.formatted_metrics and stock_details.formatted_metrics.get("cmp"):
                            cmp_value = stock_details.formatted_metrics.get("cmp", "0")
                            # Clean up the price by removing currency symbols
                            clean_price = cmp_value.replace("₹", "").replace("$", "").replace(",", "").strip()
                            current_price = float(clean_price)
                            
                            # Calculate values
                            current_value = current_price * holding.quantity
                            investment_value = holding.average_price * holding.quantity
                            gain_loss = current_value - investment_value
                            gain_loss_percentage = (gain_loss / investment_value) * 100 if investment_value > 0 else 0
                            
                            # Create enriched holding
                            enriched_holding = EnrichedHolding(
                                **holding.model_dump(),
                                current_price=current_price,
                                current_value=current_value,
                                gain_loss=gain_loss,
                                gain_loss_percentage=gain_loss_percentage,
                                has_error=False
                            )
                            enriched_holdings.append(enriched_holding)
                            continue
                            
                    # If we got here, we couldn't process the stock details properly
                    error_message = "Could not fetch current price data"
                    if isinstance(stock_details, dict) and "error" in stock_details:
                        error_message = stock_details["error"]
                        
                    fallback_holding = self._create_fallback_holding(holding, error_message)
                    enriched_holdings.append(fallback_holding)
                        
                except Exception as e:
                    logger.warning(f"Error enriching holding for {holding.symbol}: {str(e)}")
                    fallback_holding = self._create_fallback_holding(
                        holding, 
                        f"Error processing price data: {str(e)}"
                    )
                    enriched_holdings.append(fallback_holding)
            
            return enriched_holdings
            
        except Exception as e:
            logger.error(f"Error fetching batch enriched holdings: {e}")
            raise

    def _create_fallback_holding(self, holding: Holding, error_message: str) -> EnrichedHolding:
        """Create a fallback holding when price data can't be fetched"""
        investment_value = holding.average_price * holding.quantity
        return EnrichedHolding(
            **holding.model_dump(),
            current_price=holding.average_price,  # Use purchase price as fallback
            current_value=investment_value,
            gain_loss=0,
            gain_loss_percentage=0,
            has_error=True,
            error_message=error_message
        ) 