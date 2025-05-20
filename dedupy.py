#!/usr/bin/env python
# coding: utf-8

# In[ ]:


#!/usr/bin/env python3
import argparse
import pandas as pd
import hashlib
import re
import nltk
from datasketch import MinHash, MinHashLSH

# Ensure NLTK data is present (run once):
# python -m nltk.downloader punkt stopwords
from nltk.corpus import stopwords

STOPWORDS = set(stopwords.words('english'))


def preprocess(text: str) -> list[str]:
    """
    Normalize and tokenize text:
      - Lowercase
      - Remove HTML tags
      - Remove non-alphanumeric chars
      - Tokenize
      - Remove stopwords & short tokens
    """
    text = (text or "").lower()
    text = re.sub(r"<.*?>", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = nltk.word_tokenize(text)
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def detect_exact_duplicates(df: pd.DataFrame) -> pd.Series:
    """
    Return a Series mapping each index to the article_id of its first exact duplicate.
    """
    hash_map: dict[str, str] = {}
    result = {}
    for idx, text in df['normalized'].items():
        h = hashlib.sha256(text.encode('utf-8')).hexdigest()
        first = hash_map.get(h)
        if first is None:
            first = df.at[idx, 'article_id']
            hash_map[h] = first
        result[idx] = first
    return pd.Series(result)


def detect_near_duplicates(
    df: pd.DataFrame,
    num_perm: int,
    threshold: float,
    shingle_size: int
) -> pd.Series:
    """
    Return a Series mapping each index to the representative article_id
    of its near-duplicate cluster (via MinHash + LSH).
    """
    lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
    minhashes: dict[int, MinHash] = {}

    # Build signatures & insert into LSH
    for idx, tokens in df['tokens'].items():
        shingles = (
            [' '.join(tokens[i:i+shingle_size])
             for i in range(len(tokens)-shingle_size+1)]
            if len(tokens) >= shingle_size else tokens
        )
        m = MinHash(num_perm=num_perm)
        for s in set(shingles):
            m.update(s.encode('utf-8'))
        minhashes[idx] = m
        lsh.insert(idx, m)

    # Cluster and pick representative by smallest integer ID
    cluster_map: dict[int, str] = {}
    visited = set()
    for idx in df.index:
        if idx in visited:
            continue
        group = set(lsh.query(minhashes[idx]))
        # choose rep = min as integer
        rep_id = str(
            min(int(df.at[i, 'article_id']) for i in group)
        )
        for i in group:
            cluster_map[i] = rep_id
            visited.add(i)
    return pd.Series(cluster_map)


def main():
    parser = argparse.ArgumentParser(description='News Article Deduplication')
    parser.add_argument('--input',  required=True,
                        help='Path to input CSV')
    parser.add_argument('--output', required=True,
                        help='Path for output CSV')
    parser.add_argument('--threshold', type=float, default=0.8,
                        help='Jaccard sim. threshold for near duplicates')
    parser.add_argument('--shingle-size', type=int, default=5,
                        help='Number of words per shingle (default: 5)')
    parser.add_argument('--num-perm', type=int, default=128,
                        help='Number of permutations for MinHash (default: 128)')
    parser.add_argument('--block-by-date', action='store_true',
                        help='Only compare near duplicates within same publication_date')
    args = parser.parse_args()

    df = pd.read_csv(args.input, dtype={'article_id': str})

    # Preprocess
    df['tokens'] = (
        df['title'].fillna('') + ' ' + df['content_snippet'].fillna('')
    ).apply(preprocess)
    df['normalized'] = df['tokens'].apply(lambda toks: ' '.join(toks))

    # Exact duplicates
    df['exact_duplicate_of'] = detect_exact_duplicates(df)

    # Near duplicates, optionally blocked by date
    near = pd.Series(dtype=str)
    if args.block_by_date and 'publication_date' in df:
        for date, sub in df.groupby('publication_date'):
            near_sub = detect_near_duplicates(
                sub,
                num_perm=args.num_perm,
                threshold=args.threshold,
                shingle_size=args.shingle_size
            )
            near = near.append(near_sub)
    else:
        near = detect_near_duplicates(
            df,
            num_perm=args.num_perm,
            threshold=args.threshold,
            shingle_size=args.shingle_size
        )
    df['near_duplicate_of'] = near.sort_index()

    # Select only the required output columns
    output_cols = [
        'article_id', 'title', 'publication_date',
        'source_url', 'content_snippet',
        'exact_duplicate_of', 'near_duplicate_of'
    ]
    df.to_csv(args.output, columns=output_cols, index=False)
    print(f'✅ Deduplication complete. Output: {args.output}')


if __name__ == '__main__':
    main()

