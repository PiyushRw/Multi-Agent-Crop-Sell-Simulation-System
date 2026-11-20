"""
FAOSTAT Data Ingestion Module

Loads and parses FAOSTAT bulk download CSV files into clean pandas DataFrames.
Supports Production (QCL), Producer Prices (PP), and Value of Production (QV) datasets.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd
import zipfile
import logging

logger = logging.getLogger(__name__)


class FAOSTATLoader:
    """Loads FAOSTAT bulk download datasets from ZIP files."""

    # Dataset configurations
    DATASETS = {
        'production': {
            'zip_name': 'production_crops_livestock.zip',
            'data_file': 'Production_Crops_Livestock_E_All_Data_(Normalized).csv',
            'elements': {
                'area_harvested': 5312,
                'production_qty': [5510, 5513],  # Different units
                'yield': [5412, 5413, 5422],     # Different units
            },
            'key_columns': ['Area Code', 'Area', 'Item Code', 'Item', 'Element Code', 'Element', 'Year', 'Unit', 'Value'],
        },
        'prices': {
            'zip_name': 'producer_prices.zip',
            'data_file': 'Prices_E_All_Data_(Normalized).csv',
            'elements': {
                'price_lcu': 5530,      # Producer Price (LCU/tonne)
                'price_slc': 5531,      # Producer Price (SLC/tonne)
                'price_usd': 5532,      # Producer Price (USD/tonne)
                'price_index': 5539,    # Producer Price Index (2014-2016=100)
            },
            'key_columns': ['Area Code', 'Area', 'Item Code', 'Item', 'Element Code', 'Element', 'Year', 'Months', 'Unit', 'Value'],
        },
        'value': {
            'zip_name': 'value_of_production.zip',
            'data_file': 'Value_of_Production_E_All_Data_(Normalized).csv',
            'elements': {
                'value_constant_intl': [55, 152],  # Gross Production Value (constant 2014-2016 thousand Int$)
                'value_current_usd': 57,           # Gross Production Value (current thousand US$)
                'value_current_slc': 56,           # Gross Production Value (current thousand SLC)
            },
            'key_columns': ['Area Code', 'Area', 'Item Code', 'Item', 'Element Code', 'Element', 'Year', 'Unit', 'Value'],
        },
    }

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self._cache: Dict[str, pd.DataFrame] = {}

    def load_dataset(self, dataset_key: str, force_reload: bool = False) -> pd.DataFrame:
        """Load a FAOSTAT dataset, returning the main data DataFrame."""
        if dataset_key in self._cache and not force_reload:
            return self._cache[dataset_key]

        if dataset_key not in self.DATASETS:
            raise ValueError(f"Unknown dataset: {dataset_key}. Available: {list(self.DATASETS.keys())}")

        config = self.DATASETS[dataset_key]
        zip_path = self.data_dir / config['zip_name']

        if not zip_path.exists():
            raise FileNotFoundError(f"Dataset ZIP not found: {zip_path}")

        logger.info(f"Loading {dataset_key} from {zip_path}")

        with zipfile.ZipFile(zip_path, 'r') as z:
            with z.open(config['data_file']) as f:
                df = pd.read_csv(f, encoding='latin1', low_memory=False)

        # Clean column names
        df.columns = df.columns.str.strip()

        # Ensure numeric columns
        numeric_cols = ['Area Code', 'Item Code', 'Element Code', 'Year', 'Value']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        if 'Months Code' in df.columns:
            df['Months Code'] = pd.to_numeric(df['Months Code'], errors='coerce')

        self._cache[dataset_key] = df
        logger.info(f"Loaded {dataset_key}: {len(df):,} rows, {df['Area'].nunique()} areas, {df['Item'].nunique()} items, {df['Year'].min()}-{df['Year'].max()} years")

        return df

    def get_production_data(self, item_codes: Optional[List[int]] = None,
                            area_codes: Optional[List[int]] = None,
                            years: Optional[List[int]] = None,
                            elements: Optional[List[int]] = None) -> pd.DataFrame:
        """Get filtered production data."""
        df = self.load_dataset('production')

        if elements is None:
            elements = [5312, 5510, 5513, 5412, 5413, 5422]  # Area, Production, Yield

        mask = df['Element Code'].isin(elements)
        if item_codes:
            mask &= df['Item Code'].isin(item_codes)
        if area_codes:
            mask &= df['Area Code'].isin(area_codes)
        if years:
            mask &= df['Year'].isin(years)

        return df[mask].copy()

    def get_price_data(self, item_codes: Optional[List[int]] = None,
                       area_codes: Optional[List[int]] = None,
                       years: Optional[List[int]] = None,
                       elements: Optional[List[int]] = None,
                       months: Optional[List[int]] = None) -> pd.DataFrame:
        """Get filtered price data."""
        df = self.load_dataset('prices')

        if elements is None:
            elements = [5530, 5531, 5532, 5539]  # All price elements

        mask = df['Element Code'].isin(elements)
        if item_codes:
            mask &= df['Item Code'].isin(item_codes)
        if area_codes:
            mask &= df['Area Code'].isin(area_codes)
        if years:
            mask &= df['Year'].isin(years)
        if months:
            mask &= df['Months Code'].isin(months)

        return df[mask].copy()

    def get_value_data(self, item_codes: Optional[List[int]] = None,
                       area_codes: Optional[List[int]] = None,
                       years: Optional[List[int]] = None,
                       elements: Optional[List[int]] = None) -> pd.DataFrame:
        """Get filtered value of production data."""
        df = self.load_dataset('value')

        if elements is None:
            elements = [55, 152, 57, 56]  # All value elements

        mask = df['Element Code'].isin(elements)
        if item_codes:
            mask &= df['Item Code'].isin(item_codes)
        if area_codes:
            mask &= df['Area Code'].isin(area_codes)
        if years:
            mask &= df['Year'].isin(years)

        return df[mask].copy()

    def get_item_catalog(self, dataset_key: str = 'production') -> pd.DataFrame:
        """Get item code catalog for a dataset."""
        config = self.DATASETS[dataset_key]
        zip_path = self.data_dir / config['zip_name']

        data_file = config['data_file']
        if 'Prices' in data_file:
            item_file = 'Prices_E_ItemCodes.csv'
        elif 'Value_of_Production' in data_file:
            item_file = 'Value_of_Production_E_ItemCodes.csv'
        else:
            item_file = data_file.replace('All_Data', 'ItemCodes')

        with zipfile.ZipFile(zip_path, 'r') as z:
            with z.open(item_file) as f:
                return pd.read_csv(f, encoding='latin1')

    def get_area_catalog(self, dataset_key: str = 'production') -> pd.DataFrame:
        """Get area/country code catalog for a dataset."""
        config = self.DATASETS[dataset_key]
        zip_path = self.data_dir / config['zip_name']

        data_file = config['data_file']
        if 'Prices' in data_file:
            area_file = 'Prices_E_AreaCodes.csv'
        elif 'Value_of_Production' in data_file:
            area_file = 'Value_of_Production_E_AreaCodes.csv'
        else:
            area_file = data_file.replace('All_Data', 'AreaCodes')

        with zipfile.ZipFile(zip_path, 'r') as z:
            with z.open(area_file) as f:
                return pd.read_csv(f, encoding='latin1')

    def get_element_catalog(self, dataset_key: str = 'production') -> pd.DataFrame:
        """Get element code catalog for a dataset."""
        config = self.DATASETS[dataset_key]
        zip_path = self.data_dir / config['zip_name']

        # Different naming patterns for different datasets
        data_file = config['data_file']
        if 'Prices' in data_file:
            element_file = 'Prices_E_Elements.csv'
        elif 'Value_of_Production' in data_file:
            element_file = 'Value_of_Production_E_Elements.csv'
        else:
            element_file = data_file.replace('All_Data', 'Elements')

        with zipfile.ZipFile(zip_path, 'r') as z:
            with z.open(element_file) as f:
                return pd.read_csv(f, encoding='latin1')


# Convenience functions for common queries
def load_faostat(data_dir: Path) -> FAOSTATLoader:
    """Create a FAOSTATLoader instance."""
    return FAOSTATLoader(data_dir)


# Common item codes for major crops
CROP_CODES = {
    'wheat': 15,
    'maize': 56,
    'rice_paddy': 27,
    'soybeans': 236,
    'barley': 44,
    'sorghum': 83,
    'potatoes': 116,
    'cassava': 125,
    'cotton': 328,
    'rapeseed': 270,
    'sunflower': 267,
    'tomatoes': 388,
    'onions': 402,
    'bananas': 486,
    'apples': 515,
    'oranges': 490,
    'grapes': 520,
    'coffee': 656,
    'cocoa': 661,
    'tea': 667,
}

# Common country codes
COUNTRY_CODES = {
    'usa': 231,
    'brazil': 21,
    'india': 100,
    'china': 351,
    'argentina': 10,
    'russia': 185,
    'ukraine': 230,
    'canada': 39,
    'australia': 14,
    'france': 75,
    'germany': 81,
    'indonesia': 101,
    'pakistan': 165,
    'bangladesh': 19,
    'mexico': 138,
    'turkey': 223,
    'nigeria': 156,
    'south_africa': 182,
    'egypt': 62,
}