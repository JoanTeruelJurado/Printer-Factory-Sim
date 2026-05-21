import random


def generate_customer_demand(
    day: int,
    signal: dict,
    retailer_prices: dict,
    base_price: float,
) -> list[tuple[str, int]]:
    """Generate customer demand orders based on scenario signals and price sensitivity.

    Args:
        day: Current simulation day
        signal: Today's market signal (has base_demand, demand_modifier)
        retailer_prices: Dict of {model_name: retail_price}
        base_price: Reference base price for price elasticity

    Returns:
        List of (model_name, quantity) tuples representing customer orders
    """
    base = signal.get("base_demand", {"mean": 5, "variance": 2})
    modifier = signal.get("demand_modifier", 1.0)
    orders: list[tuple[str, int]] = []
    for model, price in retailer_prices.items():
        mean_orders = base["mean"] * modifier
        price_factor = max(0.2, 1.0 - (price - base_price) / base_price)
        adjusted_mean = mean_orders * price_factor
        n = max(0, int(random.gauss(adjusted_mean, base["variance"])))
        orders.extend([(model, 1)] * n)
    return orders
