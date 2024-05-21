"""Contains function to handle next blocks proposal"""

import functools

from prometheus_client import Gauge, Counter
from requests.exceptions import HTTPError, RequestException

from .beacon import Beacon
from .utils import NB_SLOT_PER_EPOCH

print = functools.partial(print, flush=True)

metric_future_block_proposals_count = Gauge(
    "future_block_proposals_count",
    "Future block proposals count",
)

key_future_block_proposals_count = Gauge(
    "key_future_block_proposals_count",
    "Key future block proposals",
    ["pubkey"],
)

initialized_keys: set[str] = set()


def process_future_blocks_proposal(
    beacon: Beacon,
    our_pubkeys: set[str],
    slot: int,
    is_new_epoch: bool,
) -> int:
    """Handle next blocks proposal

    Parameters:
    beacon      : Beacon
    our_pubkeys : Set of our validators public keys
    slot        : Slot
    is_new_epoch: Is new epoch
    """

    for _key in our_pubkeys:
        if _key not in initialized_keys:
            key_future_block_proposals_count.labels(pubkey=_key)
            initialized_keys.add(_key)
    for _key in initialized_keys:
        if _key not in our_pubkeys:
            initialized_keys.remove(_key)
            key_future_block_proposals_count.remove(pubkey=_key)

    try:
        epoch = slot // NB_SLOT_PER_EPOCH
        proposers_duties_current_epoch = beacon.get_proposer_duties(epoch)
        proposers_duties_next_epoch = beacon.get_proposer_duties(epoch + 1)

        concatenated_data = (
                proposers_duties_current_epoch.data + proposers_duties_next_epoch.data
        )
    except HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - Failed to get proposer duties for epoch {epoch} or {epoch + 1}.")
        concatenated_data = []  # Assign an empty list or handle appropriately
    except RequestException as req_err:
        print(
            f"Error occurred during network request: {req_err} - Failed to get proposer duties for epoch {epoch} or {epoch + 1}.")
        concatenated_data = []  # Assign an empty list or handle appropriately
    except Exception as e:
        print(f"Unexpected error: {e} - Failed to get proposer duties for epoch {epoch} or {epoch + 1}.")
        concatenated_data = []  # Assign an empty list or handle appropriately

    filtered = [
        item
        for item in concatenated_data
        if item.pubkey in our_pubkeys and item.slot >= slot
    ]

    metric_future_block_proposals_count.set(len(filtered))
    print(filtered)
    for _key in our_pubkeys:
        key_future_block_proposals_count.labels(pubkey=_key).inc(
            len(
                [
                    item
                    for item in filtered
                    if item.pubkey == _key
                ]
            )
        )

    if is_new_epoch:
        for item in filtered:
            print(
                f"💍 Our validator {item.pubkey[:10]} is going to propose a block "
                f"at   slot {item.slot} (in {item.slot - slot} slots)"
            )

    return len(filtered)
