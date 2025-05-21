# Atharva-Karekar-TA-News-Article-Deduplication

1. **Clone or download** this repository.
2. **Install dependencies** and download NLTK data:
   ```bash
   # Install core libraries
   pip install pandas nltk datasketch
   python -m nltk.downloader punkt stopwords
   ```
3. **Run the deduplication**:
   ```bash
   python dedupy.py \
     --input  Input_dedup.csv \
     --output dedup_output.csv \
     --threshold     0.8  
   ```

---

##  Dependencies

Library    | Minimum Version |                                  
---------- | --------------- | 
Python     | 3.7+            |                                   
pandas     | latest          |                
nltk       | latest          |             
datasketch | latest          |  

After `pip install`, download required NLTK corpora exactly once:

```bash
python -m nltk.downloader punkt stopwords
```

---

##  Input CSV Format

Your input must be a comma‑separated file with **exactly** these headers (order not critical):

Column             | Type       | Description                     
----------------- | ---------- | -------------------------------
`article_id`       | string     | Unique identifier per article   
`title`            | string     | Headline or title               
`publication_date` | YYYY-MM-DD | Date published                  
`source_url`       | string     | Original article URL            
`content_snippet`  | string     | Article body or summary snippet 

Sample (`Input_dedup.csv`)

---

##  Deduplication Algorithms

### 1. Text Normalization

- **Combine** `title` + `content_snippet` into one string per article.
- **Lowercase**, **strip HTML tags**, and **remove non‑alphanumeric** characters.
- **Tokenize** into words using NLTK.
- **Remove stopwords** (e.g., "the", "and") and very short tokens (<2 characters).

### 2. Exact Duplicate Detection

- Compute **SHA‑256 hash** of the normalized text.
- Articles producing the **same hash** are **exact duplicates**.
- First occurrence of a hash becomes the canonical record; subsequent ones are flagged.

### 3. Near Duplicate Detection

- **Shingling**: break the token list into overlapping word sequences (default: 5 words each).
- **MinHash**: generate a compact sketch (`num_perm` permutations) capturing set similarity.
- **LSH**: index MinHash sketches in a locality‑sensitive hash structure with similarity threshold (default: 0.8).
- **Cluster**: for each article, query its LSH bucket mates; assign all cluster members to the smallest `article_id` as representative.

This two‑stage approach ensures:

- **Exact clones** are caught by hashing (O(n)).
- **Fuzzy matches** are found sub‑quadratically via MinHash + LSH.

---

##  Output CSV Format

The script writes an output CSV with these columns:

Column               | Description                                                             
-------------------- | -----------------------------------------------------------------------
`article_id`         | Original article ID                                                     
`title`              | Original headline                                                       
`publication_date`   | Original publication date                                                
`source_url`         | Original URL                                                           
`content_snippet`    | Original snippet                                                         
`exact_duplicate_of` | `article_id` of the first exact duplicate (self if unique)              
`near_duplicate_of`  | `article_id` of the cluster representative (self if no near duplicates) 

**Interpretation**:

- If `exact_duplicate_of != article_id`, the row is an **exact duplicate** of that first ID.
- If `near_duplicate_of != article_id`, the row belongs to a **near‑duplicate cluster** headed by that ID.

Sample output (`dedup_output.csv`)

---

##  Configuration & Flags

Flag              | Default | Description                                             
----------------- | ------- | --------------------------------------------------------
`--input`         | —       | Path to input CSV (required)                            
`--output`        | —       | Path for output CSV (required)                          
`--threshold`     | 0.8     | Minimum Jaccard similarity for near duplicates          
`--shingle-size`  | 5       | Number of words per shingle                             
`--num-perm`      | 128     | Number of permutations for MinHash                       
`--block-by-date` | off     | Restrict near-dup comparison to same `publication_date`  


---

##  Assumptions & Design Choices

- **Purely algorithmic**: no external APIs or LLMs—ensures reproducibility and speed.
- **SHA‑256** for exact matches: low collision risk for text.
- **MinHash + LSH** for fuzzy matches: sub‑quadratic scalability on large corpora.
- **Integer comparison** for cluster reps: avoids lexical pitfalls ("10" vs "2").
- **Optional date blocking** to speed up extremely large datasets by grouping articles by day).

---
