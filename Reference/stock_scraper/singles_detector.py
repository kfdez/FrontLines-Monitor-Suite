"""
Singles Detector

Detects Pokemon card singles based on title and variant patterns.
"""

import re
from typing import Dict, List


class SinglesDetector:
    """Detects Pokemon card singles based on multiple criteria.

    Singles are identified by:
    - Card number patterns in title (e.g., "123/456", "001 ME")
    - Condition grading in variants (e.g., "Near Mint", "LP")
    """

    # Card number patterns
    CARD_NUMBER_PATTERN_1 = re.compile(r'\b\d{1,3}/\d{1,3}\b')  # 123/456
    CARD_NUMBER_PATTERN_2 = re.compile(r'\b\d{3}\s+[A-Z]{2,3}\b')  # 001 ME

    # Condition patterns
    CONDITION_PATTERNS = [
        re.compile(r'\bNear\s*Mint\b', re.IGNORECASE),
        re.compile(r'\bLightly\s*Played\b', re.IGNORECASE),
        re.compile(r'\bModerately\s*Played\b', re.IGNORECASE),
        re.compile(r'\bHeavily\s*Played\b', re.IGNORECASE),
        re.compile(r'\bDamaged\b', re.IGNORECASE),
        re.compile(r'\bNM\b'),
        re.compile(r'\bLP\b'),
        re.compile(r'\bMP\b'),
        re.compile(r'\bHP\b'),
        re.compile(r'\bDMG\b'),
    ]

    @classmethod
    def is_single(cls, product: Dict) -> bool:
        """Determine if a product is a Pokemon card single.

        Args:
            product: Product dictionary from Shopify API

        Returns:
            True if product appears to be a single card
        """
        title = product.get('title', '')

        # Check for card number in title
        if cls.CARD_NUMBER_PATTERN_1.search(title):
            return True
        if cls.CARD_NUMBER_PATTERN_2.search(title):
            return True

        # Check variants for condition grading
        variants = product.get('variants', [])
        for variant in variants:
            if not isinstance(variant, dict):
                continue

            variant_title = variant.get('title', '')
            for pattern in cls.CONDITION_PATTERNS:
                if pattern.search(variant_title):
                    return True

        return False

    @classmethod
    def get_card_number(cls, title: str) -> str:
        """Extract card number from title if present.

        Args:
            title: Product title

        Returns:
            Card number or empty string
        """
        match = cls.CARD_NUMBER_PATTERN_1.search(title)
        if match:
            return match.group()

        match = cls.CARD_NUMBER_PATTERN_2.search(title)
        if match:
            return match.group()

        return ""
