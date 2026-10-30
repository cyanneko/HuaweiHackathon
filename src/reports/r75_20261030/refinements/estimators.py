def adaptive_pool_weight(decayed_events):
    return .25/(1.+decayed_events)

def rate_signal(estimated_wait):
    return 64./estimated_wait
