import logging

class Trade(object):
    """
    Complete trade (buy/sell or short/cover).
    """
    def __init__(self, symbol, direction, quantity, estimated_cost, entered_at, order=None):
        """ Create new trade, which is kept on portfolio. """
        self.symbol = symbol
        self.direction = direction
        self.quantity = quantity
        self.entered_at = entered_at
        self.estimated_cost = estimated_cost

        self.entry_order = order
        self.entry_filled_quantity = 0.0
        self.entry_avg_cost = 00
        self.entry_value = 0.0
        self.entry_commission = 0.0

        self.exit_order = None
        self.exit_filled_quantity = 0.0
        self.exit_avg_cost = 0.0
        self.exit_value = 0.0
        self.exit_commission = 0.0

        self.unrealized_pnl = 0.0

    @property
    def entry_is_fully_filled(self):
        return self.entry_filled_quantity == self.quantity

    @property
    def exit_is_fully_filled(self):
        return self.exit_filled_quantity == -self.quantity

    def is_fill_relevant_to_portfolio(self, fill):
        # Returns False if fill contains info which would have been already consumed by portfolio
        if (
            (fill.direction in ('BUY', 'SHORT') and self.entry_is_fully_filled) or  # fill already reported
            (fill.direction in ('SELL', 'COVER') and self.exit_is_fully_filled) or  # fill already reported
            (abs(self.quantity) != abs(fill.quantity))  # partial fill (need abs because quantity is reversed for exit (e.g. 100 buy becomse -100 sell))
        ):
            return False
        else:
            return True

    def update_from_fill(self, fill, fake_exited_at=None):
        if fill.direction in ('BUY', 'SHORT'):
            if self.entry_is_fully_filled:
                logging.critical("entry_is_fully_filled for trade, however an open fill event has arrived. {}".format(fill))
                return

            self.entry_filled_quantity += fill.quantity
            self.entry_commission = fill.commission
            self.entry_avg_cost = fill.avg_cost
            self.entry_value = self.entry_filled_quantity*self.entry_avg_cost

            if self.entry_is_fully_filled:
                self.entry_fully_filled_at = fill.created_at
                logging.debug('{} order for {} completely filled'.format(self.direction, self.symbol))

        elif fill.direction in ('SELL', 'COVER'):
            if self.exit_is_fully_filled:
                raise AssertionError("exit_is_fully_filled for trade, however a exit fill event has arrived. {}".format(fill))
                return

            if not self.entry_is_fully_filled:
                raise AssertionError('Exiting {} trade before it even started on {}.'.format(self.symbol,fill.created_at))

            self.exit_filled_quantity += fill.quantity
            self.exit_commission = fill.commission
            self.exit_avg_cost = fill.avg_cost
            self.exit_value = self.exit_filled_quantity*self.exit_avg_cost

            if self.exit_is_fully_filled:
                self.exit_fully_filled_at = fill.created_at
                self.exited_at = fake_exited_at if fake_exited_at else fill.created_at
                self.pnl = -(self.entry_value + self.exit_value + self.entry_commission + self.exit_commission)

                logging.debug('{} order for {} completely filled. Trade exited with approximate pnl of {}.'.format(fill.direction, self.symbol, self.pnl))

                if not (self.exit_value == -self.quantity*self.exit_avg_cost and
                        self.entry_value == self.quantity*self.entry_avg_cost):
                    logging.critical('Assertion problem while closing a trade. Quantity = {}, exit_value = {}, exit_avg_cost = {}, entry_value = {}, entry_avg_cost = {}'.format(
                        self.quantity,
                        self.exit_value,
                        self.exit_avg_cost,
                        self.entry_value,
                        self.entry_avg_cost,
                    ))

    def update_exit_order(self, order):
        self.exit_order = order

    def fake_exit_trade(self, exited_at, exit_value):
        """ Used when backtesting finished and open_positions result need to be estimated """
        self.exited_at = exited_at
        self.exit_value = exit_value
        self.exit_avg_cost = exit_value/-self.quantity
        self.pnl = -(self.entry_value + self.exit_value + self.entry_commission + self.exit_commission)
