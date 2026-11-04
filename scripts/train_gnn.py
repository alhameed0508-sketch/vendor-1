"""
Train and save the MuleCatch GNN model.

Trains the GraphSAGE model on synthetic data and saves weights
to models/gnn/trained_model.pt for fast loading at runtime.

Usage:
    python scripts/train_gnn.py [--epochs 100] [--clusters 5] [--legit 50]
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.synthetic.generator import build_full_dataset
from models.temporal_weighting.smurf_weighting import score_transaction_batch
from models.gnn.gnn_model import GNNScorer, DEFAULT_MODEL_PATH


def main():
    parser = argparse.ArgumentParser(description="Train MuleCatch GNN model")
    parser.add_argument("--epochs", type=int, default=100, help="Training epochs")
    parser.add_argument("--clusters", type=int, default=5, help="Number of mule clusters")
    parser.add_argument("--legit", type=int, default=50, help="Number of legitimate accounts")
    parser.add_argument("--output", type=str, default=DEFAULT_MODEL_PATH, help="Output model path")
    args = parser.parse_args()

    print(f"Generating synthetic dataset: {args.clusters} clusters, {args.legit} legit accounts...")
    dataset = build_full_dataset(num_clusters=args.clusters, num_legit_accounts=args.legit)

    print(f"Dataset: {len(dataset['accounts'])} accounts, {len(dataset['transactions'])} transactions")
    print(f"  Mule accounts: {sum(1 for a in dataset['accounts'] if a['role'] in ('MULE', 'SOURCE', 'AGGREGATOR'))}")
    print(f"  Legitimate accounts: {sum(1 for a in dataset['accounts'] if a['role'] == 'LEGITIMATE')}")

    print("\nScoring transactions with smurf weighting...")
    smurf_scores = score_transaction_batch(dataset["transactions"])
    flagged = sum(1 for s in smurf_scores.values() if s.is_flagged)
    print(f"  Smurf-flagged: {flagged}/{len(smurf_scores)}")

    print(f"\nTraining GNN for {args.epochs} epochs...")
    scorer = GNNScorer(model_path=args.output)

    if scorer.model is None:
        print("ERROR: torch_geometric not available. Cannot train GNN.")
        sys.exit(1)

    predictions, metrics = scorer.train_and_predict(
        dataset["accounts"],
        dataset["transactions"],
        smurf_scores,
        epochs=args.epochs,
    )

    print(f"\nTraining complete:")
    print(f"  Final loss: {metrics.final_loss:.4f}")
    print(f"  Train accuracy: {metrics.train_accuracy:.2%}")
    print(f"  Epochs: {metrics.epochs}")

    gnn_flagged = sum(1 for p in predictions if p.is_flagged)
    print(f"\nGNN predictions: {gnn_flagged}/{len(predictions)} accounts flagged as mule")

    # Verify saved model loads correctly
    if os.path.exists(args.output):
        print(f"\nModel saved to: {args.output}")
        file_size = os.path.getsize(args.output)
        print(f"  File size: {file_size / 1024:.1f} KB")

        # Verify by loading into new scorer
        scorer2 = GNNScorer(model_path=args.output)
        assert scorer2.is_trained, "Failed to load saved model!"
        preds2 = scorer2.predict(
            dataset["accounts"], dataset["transactions"], smurf_scores
        )
        assert len(preds2) == len(predictions)
        print("  Load verification: PASSED")
    else:
        print(f"ERROR: Model not saved to {args.output}")
        sys.exit(1)


if __name__ == "__main__":
    main()
