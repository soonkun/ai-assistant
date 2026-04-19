# src/vector_search/schema.py
"""LanceDB PyArrow 스키마 정의 (M_07 §5.1)."""

import pyarrow as pa

EMBEDDING_DIM: int = 1024  # BGE-M3 dense

CHUNKS_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("doc_id", pa.string(), nullable=False),
        pa.field("doc_name", pa.string(), nullable=False),
        pa.field("category", pa.string(), nullable=True),
        pa.field("page", pa.int32(), nullable=True),
        pa.field("section", pa.string(), nullable=True),
        pa.field("chunk_id", pa.string(), nullable=False),  # PK 역할 (멱등 키)
        pa.field("text", pa.string(), nullable=False),
        pa.field("bbox", pa.list_(pa.float32(), 4), nullable=True),  # [x0,y0,x1,y1]
        pa.field("source_path", pa.string(), nullable=False),
        pa.field("vector", pa.list_(pa.float32(), EMBEDDING_DIM), nullable=False),
    ]
)
