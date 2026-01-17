"""
Tiger Transformer Client

This service loads the tiger-transformer model (fine-tuned FINBERT) and provides
inference for standardizing financial statement line items.
"""

import csv
import logging
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logger = logging.getLogger(__name__)


class TigerTransformerClient:
    """
    Client for the tiger-transformer model.

    Loads the model from a local path (checking ../tiger-transformer/models first)
    and provides batch inference for standardizing line items.
    """

    _instance = None
    _model = None
    _tokenizer = None
    _bs_mapping = None
    _is_mapping = None

    def __new__(cls):
        """Singleton pattern to prevent reloading the model on every request."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the client (only runs once due to singleton pattern)."""
        if self._model is None:
            self._load_model()
            self._load_mappings()

    def _load_model(self):
        """Load the transformer model and tokenizer."""
        # Define paths relative to this file
        # tiger-cafe/app/services/tiger_transformer_client.py -> f:\AIML projects
        workspace_root = Path(__file__).parent.parent.parent.parent
        tiger_transformer_dir = workspace_root / "tiger-transformer"

        # Valid locations
        local_model_path = tiger_transformer_dir / "models" / "financial_transformer"
        label_map_path = tiger_transformer_dir / "models" / "label_map.json"

        if local_model_path.exists():
            print(f"TigerTransformer: Loading model from local path: {local_model_path}")
            model_path = str(local_model_path)

            # Load tokenizer and model
            try:
                self._tokenizer = AutoTokenizer.from_pretrained(model_path)  # nosec B615
                self._model = AutoModelForSequenceClassification.from_pretrained(model_path)  # nosec B615
            except Exception as e:
                print(f"TigerTransformer: Failed to load local model files: {e}")
                # Fallback or re-raise? Given USER instruction "WE ARE NOT USING HUGGING FACE", raise.
                raise

            # Load label mapping if available
            if label_map_path.exists():
                import json

                try:
                    with open(label_map_path, encoding="utf-8") as f:
                        label2id = json.load(f)

                    # Create reverse mapping (id2label)
                    id2label = {int(v): k for k, v in label2id.items()}

                    # Update model config
                    self._model.config.id2label = id2label
                    self._model.config.label2id = label2id
                    print(f"TigerTransformer: Loaded label mapping with {len(id2label)} labels")
                except Exception as e:
                    print(f"TigerTransformer: Failed to load label map: {e}")
            else:
                print(f"TigerTransformer: Warning - label_map.json not found at {label_map_path}")

        else:
            print(f"TigerTransformer: Local model not found at {local_model_path}")
            # Fallback to HuggingFace if local is missing (though user said NOT using HF)
            print("TigerTransformer: Loading from HuggingFace (Ruinius/tiger-transformer)...")
            model_path = "Ruinius/tiger-transformer"
            self._tokenizer = AutoTokenizer.from_pretrained(model_path)  # nosec B615
            self._model = AutoModelForSequenceClassification.from_pretrained(model_path)  # nosec B615

        try:
            # Move to GPU if available
            if torch.cuda.is_available():
                self._model = self._model.cuda()
                print("TigerTransformer: Model loaded on GPU")
            else:
                print("TigerTransformer: Model loaded on CPU")

            self._model.eval()  # Set to evaluation mode
            print("TigerTransformer: Model loaded successfully")

        except Exception as e:
            print(f"TigerTransformer: Failed to initialize model: {e}")
            raise

    def _load_mappings(self):
        """Load the CSV mapping files for is_calculated, is_operating, is_expense."""
        # Mappings are now in app/services
        # __file__ = app/services/tiger_transformer_client.py
        # parent = app/services
        mappings_dir = Path(__file__).parent

        # Load balance sheet mapping
        bs_mapping_path = mappings_dir / "bs_calculated_operating_mapping.csv"
        self._bs_mapping = {}
        with open(bs_mapping_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self._bs_mapping[row["standardized_name"]] = {
                    "is_calculated": row["is_calculated"].lower() == "true",
                    "is_operating": row["is_operating"].lower() == "true"
                    if row["is_operating"]
                    else None,
                }

        # Load income statement mapping
        is_mapping_path = mappings_dir / "is_calculated_operating_expense_mapping.csv"
        self._is_mapping = {}
        with open(is_mapping_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self._is_mapping[row["standardized_name"]] = {
                    "is_calculated": row["is_calculated"].lower() == "true",
                    "is_operating": row["is_operating"].lower() == "true"
                    if row["is_operating"]
                    else None,
                    "is_expense": row["is_expense"].lower() == "true"
                    if row["is_expense"]
                    else None,
                }

        print(
            f"TigerTransformer: Loaded mappings from {mappings_dir}: {len(self._bs_mapping)} BS items, {len(self._is_mapping)} IS items"
        )

    def predict_balance_sheet(self, line_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Predict standardized names for balance sheet line items.

        Args:
            line_items: List of dicts with keys:
                - line_name: Original line item name
                - line_category: Section token (e.g., "current_assets")
                - line_order: Order in the statement (for context)

        Returns:
            List of dicts with added keys:
                - standardized_name: Standardized key from transformer
                - is_calculated: Boolean flag for totals/subtotals
                - is_operating: Boolean flag for operating classification
        """
        if not line_items:
            return []

        print(f"TigerTransformer: Predicting Balance Sheet for {len(line_items)} items")

        # Prepare inputs with context (2 previous + 2 next line items)
        inputs = []
        for i, item in enumerate(line_items):
            # Get context
            prev_2 = line_items[i - 2]["line_name"] if i >= 2 else "<START>"
            prev_1 = line_items[i - 1]["line_name"] if i >= 1 else "<START>"
            next_1 = line_items[i + 1]["line_name"] if i < len(line_items) - 1 else "<END>"
            next_2 = line_items[i + 2]["line_name"] if i < len(line_items) - 2 else "<END>"

            # Format: [PREV_2] [PREV_1] [SECTION] [RAW_NAME] [NEXT_1] [NEXT_2]
            input_text = (
                f"[{prev_2}] [{prev_1}] [{item['line_category']}] "
                f"[{item['line_name']}] [{next_1}] [{next_2}]"
            )
            inputs.append(input_text)

        # Run inference
        # Log exact formatted inputs
        try:
            import os

            import pandas as pd

            pd.DataFrame(inputs, columns=["formatted_input"]).to_csv(
                os.path.join(os.getcwd(), "balance_sheet_transformer_exact_inputs.csv"), index=False
            )
            print("Logged exact balance sheet inputs to balance_sheet_transformer_exact_inputs.csv")
        except Exception as e:
            print(f"Failed to log exact inputs: {e}")

        standardized_names = self._batch_inference(inputs)

        # Enrich with mapping data
        results = []
        for item, std_name in zip(line_items, standardized_names, strict=False):
            mapping_data = self._bs_mapping.get(std_name, {})
            results.append(
                {
                    **item,
                    "standardized_name": std_name,
                    "is_calculated": mapping_data.get("is_calculated"),
                    "is_operating": mapping_data.get("is_operating"),
                }
            )

        return results

    def predict_income_statement(self, line_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Predict standardized names for income statement line items.

        Args:
            line_items: List of dicts with keys:
                - line_name: Original line item name
                - line_category: Section token (e.g., "income_statement")
                - line_order: Order in the statement (for context)

        Returns:
            List of dicts with added keys:
                - standardized_name: Standardized key from transformer
                - is_calculated: Boolean flag for totals/subtotals
                - is_operating: Boolean flag for operating classification
                - is_expense: Boolean flag for expense items
        """
        if not line_items:
            return []

        print(f"TigerTransformer: Predicting Income Statement for {len(line_items)} items")

        # Prepare inputs with context (2 previous + 2 next line items)
        inputs = []
        for i, item in enumerate(line_items):
            # Get context
            prev_2 = line_items[i - 2]["line_name"] if i >= 2 else "<START>"
            prev_1 = line_items[i - 1]["line_name"] if i >= 1 else "<START>"
            next_1 = line_items[i + 1]["line_name"] if i < len(line_items) - 1 else "<END>"
            next_2 = line_items[i + 2]["line_name"] if i < len(line_items) - 2 else "<END>"

            # Format: [PREV_2] [PREV_1] [SECTION] [RAW_NAME] [NEXT_1] [NEXT_2]
            input_text = (
                f"[{prev_2}] [{prev_1}] [{item['line_category']}] "
                f"[{item['line_name']}] [{next_1}] [{next_2}]"
            )
            inputs.append(input_text)

        # Run inference
        # Log exact formatted inputs
        try:
            import os

            import pandas as pd

            pd.DataFrame(inputs, columns=["formatted_input"]).to_csv(
                os.path.join(os.getcwd(), "income_statement_transformer_exact_inputs.csv"),
                index=False,
            )
            print(
                "Logged exact income statement inputs to income_statement_transformer_exact_inputs.csv"
            )
        except Exception as e:
            print(f"Failed to log exact inputs: {e}")

        standardized_names = self._batch_inference(inputs)

        # Enrich with mapping data
        results = []
        for item, std_name in zip(line_items, standardized_names, strict=False):
            mapping_data = self._is_mapping.get(std_name, {})
            results.append(
                {
                    **item,
                    "standardized_name": std_name,
                    "is_calculated": mapping_data.get("is_calculated"),
                    "is_operating": mapping_data.get("is_operating"),
                    "is_expense": mapping_data.get("is_expense"),
                }
            )

        return results

    def _batch_inference(self, inputs: list[str]) -> list[str]:
        """
        Run batch inference on the model.

        Args:
            inputs: List of formatted input strings

        Returns:
            List of standardized names (predicted labels)
        """
        print(f"TigerTransformer: Running batch inference for {len(inputs)} inputs")

        # Tokenize inputs
        encoded = self._tokenizer(
            inputs, padding=True, truncation=True, max_length=512, return_tensors="pt"
        )

        # Move to GPU if available
        if torch.cuda.is_available():
            encoded = {k: v.cuda() for k, v in encoded.items()}

        # Run inference
        with torch.no_grad():
            outputs = self._model(**encoded)
            predictions = torch.argmax(outputs.logits, dim=-1)

        # Convert predictions to labels
        # Note: This assumes the model's config has id2label mapping
        # If not, we'll need to load the label mapping separately
        standardized_names = [self._model.config.id2label[pred.item()] for pred in predictions]

        return standardized_names
