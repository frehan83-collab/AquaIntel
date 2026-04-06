#!/usr/bin/env python
"""
Train the Temporal Fusion Transformer for salmon price prediction.

Usage:
  python scripts/train_tft.py
  python scripts/train_tft.py --epochs 50 --start-year 2015
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Suppress PyTensor noise
os.environ.setdefault("PYTENSOR_FLAGS", "device=cpu,floatX=float64,optimizer=fast_compile,cxx=")

import click


@click.command()
@click.option("--epochs", default=100, help="Max training epochs")
@click.option("--batch-size", default=32, help="Training batch size")
@click.option("--hidden-size", default=32, help="TFT hidden size")
@click.option("--start-year", default=2012, help="Start year for training data")
@click.option("--val-weeks", default=104, help="Validation weeks (held out)")
def main(epochs, batch_size, hidden_size, start_year, val_weeks):
    """Train the TFT model."""
    from config.logging_config import setup_logging
    setup_logging()

    from core.models import init_db
    init_db()

    from core.market.tft_trainer import train_tft

    print(f"Training TFT: epochs={epochs}, hidden={hidden_size}, batch={batch_size}")
    print(f"Data: start_year={start_year}, val_weeks={val_weeks}")
    print()

    result = asyncio.run(train_tft(
        epochs=epochs,
        batch_size=batch_size,
        hidden_size=hidden_size,
        start_year=start_year,
        val_weeks=val_weeks,
    ))

    print()
    print("=" * 50)
    print("TRAINING RESULTS")
    print("=" * 50)
    for k, v in result.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
