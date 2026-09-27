import polars as pl
import re
import time
from typing import Set, Tuple, Dict
from normalize import STRICT_LEGAL_SUFFIXES, clean_address, extract_street_num, extract_zip

# Frequency-filtered common stopwords to exclude from single-token blocking
GENERIC_STOP_WORDS = {
    'the', 'first', 'american', 'national', 'global', 'royal', 'star', 'apex',
    'sri', 'sai', 'om', 'new', 'city', 'shree', 'central', 'united', 'saint',
    'san', 'st', 'inc', 'corp', 'llc', 'ltd', 'pvt', 'private', 'co', 'company',
    'gmbh', 'sa', 'sas', 'sarl', 'dba', 'pvtltd', 'privatelimited', 'services',
    'service', 'enterprises', 'enterprise', 'solutions', 'group', 'industries',
    'industry', 'international', 'holdings', 'traders', 'trading', 'agency',
    'associates', 'consultants', 'consulting', 'india', 'us', 'france', 'center',
    'centre', 'store', 'mart', 'market', 'plaza', 'house', 'hotel', 'restaurant'
}

STRICT_LEGAL_REGEX = r'\b(' + '|'.join(STRICT_LEGAL_SUFFIXES) + r')\b'

def preprocess_for_blocking(df: pl.DataFrame) -> pl.DataFrame:
    """Preprocesses a DataFrame for high-speed Polars candidate blocking."""
    df = df.with_columns([
        pl.col('business_name').str.to_lowercase()
            .str.replace_all(r'[^a-z0-9\s]', ' ')
            .str.replace_all(STRICT_LEGAL_REGEX, ' ')
            .str.replace_all(r'\s+', ' ')
            .str.strip_chars()
            .alias('c_name'),
        pl.col('business_address').str.to_lowercase()
            .str.replace_all(r'[^a-z0-9\s]', ' ')
            .str.replace_all(r'\s+', ' ')
            .str.strip_chars()
            .alias('c_addr')
    ])
    
    # Street number and ZIP extractions
    df = df.with_columns([
        pl.col('c_addr').str.extract(r'\b(\d+[a-z]?)\b', 1).fill_null('').alias('s_num'),
        pl.col('c_addr').str.extract(r'\b(\d{5,6})\b', 1).fill_null('').alias('z_code')
    ])
    
    # Token splits
    df = df.with_columns([
        pl.col('c_name').str.split(' ').alias('name_tokens'),
        pl.col('c_addr').str.split(' ').alias('addr_tokens')
    ])
    
    # Sorted tokens
    df = df.with_columns(
        pl.col('name_tokens').list.sort().alias('sorted_tokens')
    )
    
    # Extract token elements safely
    df = df.with_columns([
        pl.col('sorted_tokens').list.get(0, null_on_oob=True).fill_null('').alias('st0'),
        pl.col('sorted_tokens').list.get(1, null_on_oob=True).fill_null('').alias('st1'),
        pl.col('sorted_tokens').list.get(2, null_on_oob=True).fill_null('').alias('st2'),
        pl.col('name_tokens').list.get(0, null_on_oob=True).fill_null('').alias('t0'),
        pl.col('addr_tokens').list.get(0, null_on_oob=True).fill_null('').alias('a0')
    ])
    
    # Construct primary blocking keys
    df = df.with_columns([
        # Key 1: Sorted first 2 tokens (handles word order)
        (pl.col('country') + '_K2_' + pl.col('st0') + '_' + pl.col('st1')).alias('k_sorted2'),
        # Key 2: Sorted first 3 tokens
        (pl.col('country') + '_K3_' + pl.col('st0') + '_' + pl.col('st1') + '_' + pl.col('st2')).alias('k_sorted3'),
        # Key 3: Street number + 4-char name prefix
        (pl.col('country') + '_KSN_' + pl.col('s_num') + '_' + pl.col('st0').str.slice(0, 4)).alias('k_sn'),
        # Key 4: ZIP code + 3-char name prefix
        (pl.col('country') + '_KZ_' + pl.col('z_code') + '_' + pl.col('st0').str.slice(0, 3)).alias('k_zip'),
        # Key 5: Street number + first address token
        (pl.col('country') + '_KADDR_' + pl.col('s_num') + '_' + pl.col('a0')).alias('k_addr'),
        # Key 6: First name token
        (pl.col('country') + '_KT0_' + pl.col('t0')).alias('k_t0')
    ])
    
    return df

def generate_candidate_pairs(
    s1_df: pl.DataFrame,
    s23_df: pl.DataFrame,
    max_t0_bucket: int = 1500
) -> pl.DataFrame:
    """Generates candidate pairs (source1_entity_id, candidate_entity_id) via multi-key join."""
    s1_prep = preprocess_for_blocking(s1_df)
    s23_prep = preprocess_for_blocking(s23_df)
    
    # 1. Join on Sorted 2 Tokens
    j1 = s1_prep.filter(pl.col('st1') != '').select(['entity_id', 'k_sorted2']).join(
        s23_prep.filter(pl.col('st1') != '').select(['entity_id', 'k_sorted2']).rename({'entity_id': 'candidate_id'}),
        on='k_sorted2', how='inner'
    ).select(['entity_id', 'candidate_id'])
    
    # 2. Join on Street Number + Name Prefix
    j2 = s1_prep.filter(pl.col('s_num') != '').select(['entity_id', 'k_sn']).join(
        s23_prep.filter(pl.col('s_num') != '').select(['entity_id', 'k_sn']).rename({'entity_id': 'candidate_id'}),
        on='k_sn', how='inner'
    ).select(['entity_id', 'candidate_id'])
    
    # 3. Join on ZIP + Name Prefix
    j3 = s1_prep.filter((pl.col('z_code') != '') & (pl.col('z_code').str.len_chars() >= 5)).select(['entity_id', 'k_zip']).join(
        s23_prep.filter((pl.col('z_code') != '') & (pl.col('z_code').str.len_chars() >= 5)).select(['entity_id', 'k_zip']).rename({'entity_id': 'candidate_id'}),
        on='k_zip', how='inner'
    ).select(['entity_id', 'candidate_id'])

    # 4. Join on Street Number + Address Token
    j4 = s1_prep.filter((pl.col('s_num') != '') & (pl.col('a0') != '')).select(['entity_id', 'k_addr']).join(
        s23_prep.filter((pl.col('s_num') != '') & (pl.col('a0') != '')).select(['entity_id', 'k_addr']).rename({'entity_id': 'candidate_id'}),
        on='k_addr', how='inner'
    ).select(['entity_id', 'candidate_id'])

    # 5. Join on First Name Token (frequency capped)
    t0_counts = s23_prep.group_by('k_t0').len()
    valid_t0 = set(t0_counts.filter((pl.col('len') >= 2) & (pl.col('len') <= max_t0_bucket))['k_t0'].to_list())
    
    s1_t0_filt = s1_prep.filter((pl.col('t0').str.len_chars() >= 3) & (~pl.col('t0').is_in(GENERIC_STOP_WORDS)) & (pl.col('k_t0').is_in(valid_t0)))
    s23_t0_filt = s23_prep.filter((~pl.col('t0').is_in(GENERIC_STOP_WORDS)) & (pl.col('k_t0').is_in(valid_t0)))
    
    j5 = s1_t0_filt.select(['entity_id', 'k_t0']).join(
        s23_t0_filt.select(['entity_id', 'k_t0']).rename({'entity_id': 'candidate_id'}),
        on='k_t0', how='inner'
    ).select(['entity_id', 'candidate_id'])

    # Combine all candidate pairs and deduplicate
    all_pairs = pl.concat([j1, j2, j3, j4, j5]).unique()
    return all_pairs
