"""
Script to analyze the distribution of financial metrics across documents.
"""
import pymongo
import logging
from collections import Counter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def analyze_metrics_distribution():
    """
    Analyze the distribution of financial metrics across documents.
    """
    # Set up MongoDB connection
    mongo_uri = "mongodb://localhost:27017"
    client = pymongo.MongoClient(mongo_uri)
    db = client.stock_data
    collection = db.detailed_financials
    
    try:
        # Count total documents
        total_docs = collection.count_documents({})
        logger.info(f"Total documents in collection: {total_docs}")
        
        # Analyze distribution of financial metrics count
        metrics_count = {}
        quarter_combinations = Counter()
        all_quarters = set()
        
        for doc in collection.find().limit(100):  # Sample first 100 documents
            metrics_len = len(doc.get('financial_metrics', []))
            if metrics_len in metrics_count:
                metrics_count[metrics_len] += 1
            else:
                metrics_count[metrics_len] = 1
            
            # Track quarter combinations
            quarters = tuple(sorted([
                metric.get('quarter') for metric in doc.get('financial_metrics', []) 
                if metric.get('quarter')
            ]))
            quarter_combinations[quarters] += 1
            
            # Track all unique quarters
            for quarter in quarters:
                all_quarters.add(quarter)
        
        logger.info(f"Distribution of financial metrics count: {metrics_count}")
        logger.info(f"All unique quarters found: {sorted(all_quarters)}")
        logger.info(f"Quarter combinations distribution:")
        for combo, count in quarter_combinations.most_common():
            logger.info(f"  {combo}: {count} documents")
        
        # Sample documents with different metrics counts
        for count in metrics_count.keys():
            sample_doc = collection.find_one({"$where": f"this.financial_metrics.length == {count}"})
            if sample_doc:
                logger.info(f"\nSample document with {count} metrics:")
                logger.info(f"Company: {sample_doc.get('company_name')}")
                
                # Show quarters for this document
                quarters = [metric.get('quarter') for metric in sample_doc.get('financial_metrics', []) if metric.get('quarter')]
                logger.info(f"Quarters: {quarters}")
                
                # Show key metrics for each quarter
                for i, metric in enumerate(sample_doc.get('financial_metrics', [])):
                    quarter = metric.get('quarter', f'Unknown-{i}')
                    logger.info(f"  Quarter {quarter}:")
                    for key in ['revenue', 'net_profit', 'revenue_growth', 'net_profit_growth']:
                        if key in metric:
                            logger.info(f"    {key}: {metric[key]}")
        
        # Check for consistency in quarter naming
        logger.info("\nChecking for consistency in quarter naming:")
        quarter_patterns = Counter()
        for doc in collection.find().limit(100):
            for metric in doc.get('financial_metrics', []):
                quarter = metric.get('quarter')
                if quarter:
                    quarter_patterns[quarter] += 1
        
        logger.info(f"Quarter naming patterns found:")
        for pattern, count in quarter_patterns.most_common(10):
            logger.info(f"  {pattern}: {count} occurrences")
        
    except Exception as e:
        logger.error(f"Error analyzing metrics distribution: {str(e)}")
    finally:
        # Close MongoDB connection
        client.close()
        logger.info("MongoDB connection closed")

if __name__ == "__main__":
    analyze_metrics_distribution() 