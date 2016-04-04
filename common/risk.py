import logging
from math import floor

from hyzou.LiveTrading.utils import _round

class RiskAnalysis(object):
    def __init__(self, settings_dict, cash_balance_method, net_liquidation_method):

        [setattr(self, key, val) for key, val in settings_dict.items()]
        self.cash_balance = cash_balance_method
        self.net_liquidation = net_liquidation_method

    def adjust_price_for_slippage(self, direction, price):
        direction_mod = -1 if direction in ('SELL','SHORT') else 1
        return _round(price * (1+self.MAX_SLIPPAGE*direction_mod))

    def determine_commission(self, quantity, price):
        return max(self.COMMISSION_FIXED + (self.COMMISSION_PCT * abs(quantity) * price), self.COMMISSION_MIN)

    def calculate_quantity_and_commission(self, direction, price, current_quantity=None):
        direction_mod = -1 if direction in ('SELL','SHORT') else 1
        quantity = 0
        estimated_commission = 0
        cash_balance = self.cash_balance()
        net_liquidation = self.net_liquidation()

        if direction in ('BUY', 'SHORT'):

            # Cash to be spent on this position
            if self.CAPITAL_TRADABLE_CAP:
                position_cash = min(self.CAPITAL_TRADABLE_CAP, net_liquidation)*self.POSITION_SIZE
            else:
                position_cash = net_liquidation*self.POSITION_SIZE

            # Adjust position down if not enough money and
            if direction == 'BUY':
                if position_cash > cash_balance:
                    if self.ADJUST_POSITION_DOWN:
                        position_cash = cash_balance
                    else:
                        logging.warning("Can't adjust position, {} missing cash.".format(str(position_cash-cash_balance)))
                        return 0, 0

            # Check if position_cash if higher than COMMISSION_MIN, otherwise ignore signal
            if self.COMMISSION_MIN > position_cash:
                logging.critical("Commission minimum is higher than available position cash, ignoring signal")
                return 0, 0

            quantity = direction_mod * position_cash / price
            quantity = floor(quantity/self.ROUND_LOT_SIZE) * self.ROUND_LOT_SIZE if self.ROUND_LOT_SIZE else quantity
            estimated_commission = self.determine_commission(quantity, price)

            # Adjust position down if position_cash isn't enough for cost + commissions
            if direction == 'BUY' and quantity * price + estimated_commission > position_cash:
                position_cash = position_cash - estimated_commission

                quantity = direction_mod * position_cash / price
                quantity = floor(quantity/self.ROUND_LOT_SIZE) * self.ROUND_LOT_SIZE if self.ROUND_LOT_SIZE else quantity
                estimated_commission = self.determine_commission(quantity, price)

                if self.ROUND_LOT_SIZE >= 1:  # any round lot size smaller than one might take too long to adjust
                    new_quantity = quantity + self.ROUND_LOT_SIZE
                    new_estimated_commission = self.determine_commission(quantity, price)
                    while True:
                        if new_quantity * price + new_estimated_commission < position_cash:
                            quantity = new_quantity
                            estimated_commission = new_estimated_commission
                        else:
                            break

            # Removed bacause it was causing performance problems, and indeed was intended to be removed
            # Still trying to come up with a better way of doing this, but above method of adjusting once
            # seems to be working well enough (although one test will have to be adjusted)

            # # For as long as estimated cost is bigger than position_cash available
            # while estimated_commission + quantity * price > position_cash:
            #     # Adjust quantity down
            #     quantity -= self.ROUND_LOT_SIZE or 1  # What if can buy less than 1 (e.g. BTC)
            #     # Recalculate commission
            #     estimated_commission = self.determine_commission(quantity, price)

        elif direction in ('SELL', 'COVER'):
            quantity = -1 * current_quantity  # Should raise TypeError if current_quality is None
            estimated_commission =  self.determine_commission(quantity, price)

        return quantity, estimated_commission


