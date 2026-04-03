"""Recurring transaction detection using TF-IDF clustering."""
import logging
from collections import Counter
from datetime import date

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer


logger = logging.getLogger(__name__)


class RecurringTransactionDetector:
    """Detect recurring transactions from history using description clustering
    and interval regularity analysis.

    Uses TF-IDF vectorization of transaction descriptions followed by DBSCAN
    clustering with cosine distance, then sub-groups by amount within each
    description cluster, and finally filters by timing regularity.
    """

    FREQUENCY_RANGES = [
        (5, 9, "weekly"),
        (12, 18, "fortnightly"),
        (25, 35, "monthly"),
        (55, 100, "quarterly"),
        (160, 200, "semi_annual"),
        (340, 400, "annual"),
    ]

    def __init__(self, min_cluster_size=3, interval_cv_threshold=0.35,
                 cosine_distance_threshold=0.4, amount_tolerance=0.10,
                 **kwargs):
        self.min_cluster_size = min_cluster_size
        self.interval_cv_threshold = interval_cv_threshold
        # Accept legacy 'similarity_threshold' kwarg for backwards compat
        self.cosine_distance_threshold = kwargs.get(
            'similarity_threshold', cosine_distance_threshold
        )
        # Fraction of median amount used as DBSCAN eps for amount sub-grouping.
        # E.g. 0.10 means amounts within 10% of the median are grouped together,
        # allowing for gradual price increases over time.
        self.amount_tolerance = amount_tolerance

    def _classify_frequency(self, mean_days):
        """Classify a mean interval in days to a frequency label."""
        for low, high, label in self.FREQUENCY_RANGES:
            if low <= mean_days <= high:
                return label
        return "irregular"

    def _classify_amount_type(self, amounts):
        """Classify amount variability."""
        abs_amounts = np.abs(amounts)
        mean = np.mean(abs_amounts)
        if mean == 0:
            return "fixed"
        cv = np.std(abs_amounts) / mean
        if cv < 0.05:
            return "fixed"
        elif cv < 0.3:
            return "variable_low"
        return "variable_high"

    def _sub_group_by_amount(self, cluster_txs):
        """Split a description cluster into sub-groups by similar amounts.

        Uses DBSCAN on absolute amounts with eps derived from the median
        amount and the configured tolerance. This separates interleaved
        payment series that share the same description but have distinct
        amounts (e.g. two gym memberships billed on the same day).

        Returns a list of transaction lists (sub-groups).
        """
        abs_amounts = np.array([abs(t['amount']) for t in cluster_txs])
        median_amount = np.median(abs_amounts)

        # If all amounts are very close, no need to sub-group
        if median_amount == 0:
            return [cluster_txs]

        # Use DBSCAN on 1D absolute amounts.
        # The tolerance-based eps handles gradual price increases
        # (e.g. $113.07 → $115.78) while still separating distinct series
        # (e.g. $100 vs $113).
        eps = max(median_amount * self.amount_tolerance, 0.01)
        amount_features = abs_amounts.reshape(-1, 1)
        clustering = DBSCAN(eps=eps, min_samples=self.min_cluster_size)
        labels = clustering.fit_predict(amount_features)

        sub_groups = {}
        noise = []
        for i, label in enumerate(labels):
            if label == -1:
                noise.append(cluster_txs[i])
            else:
                sub_groups.setdefault(label, []).append(cluster_txs[i])

        result = list(sub_groups.values())

        # If DBSCAN found no sub-groups (all noise), fall back to the
        # original cluster as a single group
        if not result:
            return [cluster_txs]

        return result

    def _analyze_group(self, txs, cluster_id, sub_id=None):
        """Analyze a group of transactions for regularity and build result dict.

        Returns the group dict if it passes regularity checks, else None.
        """
        txs.sort(key=lambda t: t['when'])

        dates = [t['when'] for t in txs]
        if len(dates) < 2:
            return None

        intervals = []
        for i in range(1, len(dates)):
            delta = (dates[i] - dates[i - 1]).total_seconds() / 86400
            intervals.append(delta)

        intervals = np.array(intervals)
        mean_interval = np.mean(intervals)
        if mean_interval == 0 or not np.isfinite(mean_interval):
            return None

        std_interval = np.std(intervals)
        interval_cv = std_interval / mean_interval

        # Filter by regularity
        if interval_cv > self.interval_cv_threshold:
            return None

        # Amount analysis
        amounts = np.array([t['amount'] for t in txs])
        amount_mean = float(np.mean(amounts))
        amount_std = float(np.std(amounts))
        amount_type = self._classify_amount_type(amounts)

        # Representative description
        desc_counter = Counter(t['description'] for t in txs)
        description_pattern = desc_counter.most_common(1)[0][0]
        sample_descriptions = [
            desc for desc, _ in desc_counter.most_common(5)
        ]

        # Category inference: most common non-null category
        cat_counter = Counter(
            (t['category_id'], t['category_name'])
            for t in txs
            if t['category_id'] is not None
        )
        if cat_counter:
            (cat_id, cat_name), _ = cat_counter.most_common(1)[0]
        else:
            cat_id, cat_name = None, None

        # Frequency classification
        frequency = self._classify_frequency(mean_interval)

        # Regularity score
        regularity_score = max(0.0, 1.0 - interval_cv)

        # Build group ID: if sub-grouped, use "cluster_id.sub_id"
        group_id = cluster_id if sub_id is None else cluster_id * 100 + sub_id

        return {
            'cluster_id': int(group_id),
            'description_pattern': description_pattern,
            'sample_descriptions': sample_descriptions,
            'frequency': frequency,
            'mean_interval_days': round(float(mean_interval), 1),
            'interval_cv': round(float(interval_cv), 3),
            'regularity_score': round(float(regularity_score), 3),
            'amount_mean': round(amount_mean, 2),
            'amount_std': round(amount_std, 2),
            'amount_type': amount_type,
            'is_income': amount_mean > 0,
            'transaction_count': len(txs),
            'transaction_ids': [t['id'] for t in txs],
            'first_date': txs[0]['when'].date() if hasattr(txs[0]['when'], 'date') else txs[0]['when'],
            'last_date': txs[-1]['when'].date() if hasattr(txs[-1]['when'], 'date') else txs[-1]['when'],
            'category': cat_id,
            'category_name': cat_name,
        }

    def detect(self, transactions_qs):
        """Detect recurring transaction groups from a queryset.

        Args:
            transactions_qs: A Transaction queryset (should already be filtered
                for date range, is_split=False, description not null/empty).

        Returns:
            List of dicts, each representing a detected recurring group.
        """
        transactions = list(
            transactions_qs.values_list(
                'id', 'when', 'amount', 'description', 'category', 'category__name'
            ).order_by('when')
        )

        if len(transactions) < self.min_cluster_size:
            return []

        # Extract descriptions, filtering out any remaining empties
        tx_data = []
        for tx_id, when, amount, desc, cat_id, cat_name in transactions:
            if desc and desc.strip():
                tx_data.append({
                    'id': tx_id,
                    'when': when,
                    'amount': float(amount),
                    'description': desc.strip(),
                    'category_id': cat_id,
                    'category_name': cat_name,
                })

        if len(tx_data) < self.min_cluster_size:
            return []

        descriptions = [t['description'] for t in tx_data]

        # Step 1: TF-IDF vectorization
        # Use max_df=1.0 because recurring transactions often have identical
        # descriptions, and max_df<1.0 would prune those common terms.
        n_unique = len(set(descriptions))
        vectorizer = TfidfVectorizer(
            lowercase=True,
            token_pattern=r'(?u)\b\w+\b',
            min_df=min(2, len(tx_data)),
            max_df=1.0 if n_unique < 20 else 0.95,
        )
        try:
            tfidf_matrix = vectorizer.fit_transform(descriptions)
        except ValueError:
            # No features extracted (all descriptions are stop words, etc.)
            return []

        # Step 2: DBSCAN clustering by description similarity
        from sklearn.metrics.pairwise import cosine_distances
        dist_matrix = cosine_distances(tfidf_matrix)
        clustering = DBSCAN(
            eps=self.cosine_distance_threshold,
            min_samples=self.min_cluster_size,
            metric='precomputed',
        )
        labels = clustering.fit_predict(dist_matrix)

        # Step 3: For each description cluster, sub-group by amount,
        # then analyze each sub-group for regularity
        groups = []
        unique_labels = set(labels)
        unique_labels.discard(-1)  # Remove noise label

        for cluster_id in sorted(unique_labels):
            cluster_indices = [i for i, lbl in enumerate(labels) if lbl == cluster_id]
            cluster_txs = [tx_data[i] for i in cluster_indices]

            # Sub-group by amount to separate interleaved payment series
            sub_groups = self._sub_group_by_amount(cluster_txs)

            for sub_id, sub_txs in enumerate(sub_groups):
                if len(sub_txs) < self.min_cluster_size:
                    continue

                use_sub_id = sub_id if len(sub_groups) > 1 else None
                result = self._analyze_group(sub_txs, cluster_id, use_sub_id)
                if result is not None:
                    groups.append(result)

        # Sort by regularity score descending
        groups.sort(key=lambda g: g['regularity_score'], reverse=True)
        return groups
