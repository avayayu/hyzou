import datetime

class Event(object):
    """
    Priority is
        10 Fill
        10 Order
        20 Signal
        30 Market
    """
    def __lt__(self, other):
         return (self.priority, self.created_at) < (other.priority, other.created_at)


class MarketEvent(Event):

    def __init__(self, sub_type, symbol=None, updated_field_type=None, updated_value=None):

        if sub_type not in ('before_open', 'on_open', 'during' ,'on_close', 'after_close'):
            raise ValueError("Wrong type of MarketEvent sub_type.")

        self.priority = 30
        self.sub_type = sub_type
        self.symbol = symbol
        self.updated_field_type = updated_field_type
        self.updated_value = updated_value
        self.created_at = datetime.datetime.now()


class SignalEvent(Event):

    def __init__(self, symbol, direction, price, estimated_exit_price=None, estimated_pnl=None):
        self.priority = 20
        self.symbol = symbol
        self.direction = direction
        self.price = price
        self.estimated_exit_price = estimated_exit_price
        self.estimated_pnl = estimated_pnl
        self.created_at = datetime.datetime.now()

    def __str__(self):
        if self.direction in ('BUY', 'SHORT') and self.estimated_pnl:
            return "Signal {} {} entry price {}, estimated exit price {}, estimated pnl {}".format(self.direction, self.symbol, self.price, self.estimated_exit_price, self.estimated_pnl)
        else:
            return "Signal {} {} price {}".format(self.direction, self.symbol, self.price)


class OrderEvent(Event):

    def __init__(self, symbol, direction, quantity, limit_price, order_id):

        self.priority = 10
        self.order_id = order_id
        self.type = 'LMT'
        self.symbol = symbol
        self.quantity = quantity
        self.direction = direction
        self.limit_price = limit_price
        self.created_at = datetime.datetime.now()

    def __str__(self):
        return "Order {} {} {} for {}, costing {}".format(self.direction, self.quantity, self.symbol, self.limit_price, self.quantity*self.limit_price)


class FillEvent(Event):

    def __init__(self, symbol, direction, quantity,
                 avg_cost, commission, is_existing_trade=False):

        self.priority = 10
        self.symbol = symbol
        self.direction = direction
        self.quantity = quantity
        self.avg_cost = avg_cost
        self.commission = commission
        self.is_existing_trade = is_existing_trade
        self.created_at = datetime.datetime.now()

    def __str__(self):
        if self.is_existing_trade:
            return "Existing trade loaded from broker {} {} {} for avg price {}".format(self.direction, self.quantity, self.symbol, self.avg_cost)
        else:
            return "Fill {} {} {} for avg price {}".format(self.direction, self.quantity, self.symbol, self.avg_cost)
