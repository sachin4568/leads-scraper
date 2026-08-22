from __future__ import annotations

import random
from typing import Any

INDUSTRIES = [
    "Dental",
    "Legal",
    "Plumbing",
    "Bakery",
    "Automotive",
    "E-commerce",
    "Real Estate",
    "Healthcare",
    "Fitness",
    "HVAC",
    "Beauty & Salon",
    "Services",
]

LOCATIONS = [
    "New York, NY",
    "Chicago, IL",
    "Los Angeles, CA",
    "Houston, TX",
    "Phoenix, AZ",
    "Miami, FL",
    "Boston, MA",
    "Seattle, WA",
]


class PermutationDataGenerator:
    """Generates synthetic feature permutations and real-world noisy edge cases for AI training."""

    @staticmethod
    def generate_phase_a_permutations(count: int = 10000) -> list[dict[str, Any]]:
        """Phase A: Clean & comprehensive feature permutations across 12 industries and 6 connectors."""
        samples: list[dict[str, Any]] = []

        for i in range(count):
            industry = random.choice(INDUSTRIES)
            location = random.choice(LOCATIONS)
            has_website = random.choice([0, 1])
            has_email = random.choice([0, 1])
            has_phone = random.choice([0, 1])
            has_ssl = 1 if has_website and random.random() > 0.3 else 0
            has_mobile = 1 if has_website and random.random() > 0.2 else 0

            # SEO Signals
            title_len = random.choice([0, 5, 25, 55]) if has_website else 0
            has_meta_desc = 1 if has_website and random.random() > 0.4 else 0
            has_h1 = 1 if has_website and random.random() > 0.3 else 0
            has_schema = 1 if has_website and random.random() > 0.5 else 0

            # Social & Ads
            has_social = random.choice([0, 1])
            has_meta_pixel = 1 if has_website and random.random() > 0.5 else 0
            has_google_tag = 1 if has_website and random.random() > 0.5 else 0
            active_meta_ads = random.choice([0, 1])

            # Label calculations
            website_opp = 3 if not has_website or not has_ssl else (1 if not has_mobile else 0)
            seo_opp = 3 if not has_meta_desc or title_len < 10 else (2 if not has_h1 else 0)
            ads_opp = (
                3 if active_meta_ads and not has_meta_pixel else (2 if not active_meta_ads else 1)
            )

            smma_score = int(
                (website_opp * 25) + (seo_opp * 25) + (ads_opp * 25) + (random.randint(0, 25))
            )
            smma_opp = 3 if smma_score >= 70 else (2 if smma_score >= 40 else 1)

            lead_quality = (
                4
                if (has_email and has_phone and smma_score >= 60)
                else (2 if has_email or has_phone else 1)
            )
            lead_priority = smma_opp

            samples.append(
                {
                    "sample_id": f"phase_a_{i}",
                    "industry": industry,
                    "location": location,
                    "has_website": has_website,
                    "has_email": has_email,
                    "has_phone": has_phone,
                    "has_ssl": has_ssl,
                    "has_mobile": has_mobile,
                    "title_len": title_len,
                    "has_meta_desc": has_meta_desc,
                    "has_h1": has_h1,
                    "has_schema": has_schema,
                    "has_social": has_social,
                    "has_meta_pixel": has_meta_pixel,
                    "has_google_tag": has_google_tag,
                    "active_meta_ads": active_meta_ads,
                    "website_opportunity": website_opp,
                    "seo_opportunity": seo_opp,
                    "ads_opportunity": ads_opp,
                    "smma_opportunity": smma_opp,
                    "lead_quality": lead_quality,
                    "lead_priority": lead_priority,
                    "is_noisy": False,
                }
            )

        return samples

    @staticmethod
    def generate_phase_b_noisy_samples(count: int = 30000) -> list[dict[str, Any]]:
        """Phase B: Noisy edge cases, missing fields, corrupted signals, and negative samples."""
        clean_samples = PermutationDataGenerator.generate_phase_a_permutations(count=count)
        noisy_samples: list[dict[str, Any]] = []

        for idx, s in enumerate(clean_samples):
            noisy = dict(s)
            noisy["sample_id"] = f"phase_b_{idx}"
            noisy["is_noisy"] = True

            # Inject 40% negative rejection sampling
            if random.random() < 0.4:
                noisy["has_email"] = 0
                noisy["has_phone"] = 0
                noisy["lead_quality"] = 0
                noisy["lead_priority"] = 0
                noisy["rejection_reason"] = random.choice(
                    [
                        "No contact information",
                        "Out of service business",
                        "Spam entry",
                        "Corrupted HTML payload",
                    ]
                )
            else:
                # Inject signal conflicts
                if random.random() < 0.2:
                    noisy["has_website"] = 0
                    noisy["active_meta_ads"] = 1  # Conflict: running ads with no website
                    noisy["smma_opportunity"] = 3
                    noisy["lead_quality"] = 3

            noisy_samples.append(noisy)

        return noisy_samples
