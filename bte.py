#!/usr/bin/env python
#Ticker Printout#
# Created by genBTC 4/12/2013

import urllib
import json
import time
import sqlite3
import matplotlib.pyplot as plt

from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle


class Ema:
    def __init__(self, alpha):
        self.avg = 0.0;
        self.lastEma = 0.0;
        self.alpha = alpha;

    def update(self, last):
        if self.ema == 0 :
            self.ema      = last;
            self.lastEma  = last;
        else :
            self.lastEma = self.ema;
            self.ema = self.lastEma * self.alpha + (1 - self.alpha) * last;

class Ma:
    def __init__(self, num):
        self.avg = 0.0;
        self.num = num;
        self.hist = list();

    def update(self, last):
        self.hist.append(last);
        if len(self.hist) > self.num :
            self.hist.pop(0);

    def get(self):
        if len(self.hist) == self.num :
            self.avg = 0;
            for x in range(0, self.num):
                self.avg = self.avg + self.hist[x];
            self.avg = self.avg / self.num;
            return self.avg;
        else :
            return None;


class Trade:
    def __init__(self, sell, buy, last, txid):
        self.sell = sell;
        self.buy = buy;
        self.last = last;
        self.txid = txid;

class mtgoxTicker:
    def __init__(self, currency, delaytime):
        self.cur = currency;
        self.delay = delaytime;
        self.url = "http://data.mtgox.com/api/1/BTC" + currency + "/ticker_fast";
        self.lastTrade = Trade(0,0,0,0);

    def getLatest(self):
        while True :
            req = urllib.request.Request(self.url)
            resp = urllib.request.urlopen(req)

            data = json.load(resp)
            t = Trade(float(data["return"]["buy"]["value"]),
                                     float(data["return"]["sell"]["value"]),
                                     float(data["return"]["last"]["value"]),
                                     data["return"]["now"].encode('utf-8'));
            if(t.txid != self.lastTrade.txid) :
                self.lastTrade = t;
                return t;
            time.sleep(self.delay);

class sqliteTicker:
    def __init__(self, currency, startTid, duration):
        self.cur = currency;
        self.db = sqlite3.connect('mtgox.sqlite3')
        self.db.execute('PRAGMA checkpoint_fullfsync=false')
        self.db.execute('PRAGMA fullfsync=false')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=off')
        self.db.execute('PRAGMA temp_store=MEMORY')

        self.cursor = self.db.cursor()
        self.cursor.execute("SELECT price,tid FROM trades WHERE currency=? AND tid>? AND tid<? ORDER BY tid ASC",(self.cur,startTid*1000000,(startTid+duration)*1000000,))

    def getLatest(self):
        row = self.cursor.fetchone();
        if row is not None:
            price = float(row[0]);
            tid = int(row[1]);
            return Trade(price*0.999,price,price*1.001,tid);
        return None;

class Account:
    def __init__(self, btc, fiat, fee, trade):
        self.btc  = btc;
        self.fiat = fiat;
        self.fee  = fee;
        self.lastOrder = trade;
        self.buyOrders = list();
        self.sellOrders = list();

    def buy(self, trade):
        if(self.fiat > 0) :
            self.btc = (self.fiat / trade.buy) * self.fee;
            print("buy  {:01.4f} BTC for {:8.2f} Fiat. Price is {:8.2f}.  ".format(self.btc, self.fiat, trade.buy)+time.ctime(int(trade.txid/1000000)));
            self.fiat = 0;
            self.lastOrder = trade;
            self.buyOrders.append([trade.buy, trade.txid]);
            return True;
        else :
            return False;

    def sell(self, trade):
        if(self.btc > 0) :
            self.fiat = (self.btc * trade.sell) * self.fee;
            print("sell {:01.4f} BTC for {:8.2f} Fiat. Price is {:8.2f}.  ".format(self.btc, self.fiat, trade.buy)+time.ctime(int(trade.txid/1000000)));
            self.btc = 0;
            self.lastOrder = trade;
            self.sellOrders.append([trade.sell, trade.txid]);
            return True;
        else :
            return False;

class CandleStick:
    def __init__(self):
        self.high   = 0;
        self.low    = 1000000.0;
        self.open   = 0;
        self.close  = 0;
        self.count  = 0;
        self.first  = 0;
        self.last   = 0;
    def __str__(self):
        return "Open "+str(self.open)+", High "+str(self.high)+", Low "+str(self.low)+", Close "+str(self.close);
    def update(self, trade):
        if self.open == 0 :
            self.open   = trade.last;
            self.first  = trade.txid;
        if trade.last > self.high : self.high = trade.last;
        if trade.last < self.low  : self.low = trade.last;
        self.close = trade.last;
        self.last  = trade.txid;
        self.count = self.count + 1;


class CandleStickChart:
    def __init__(self, numberOfCandles, durationOfCandle):
        self.maxListLen = numberOfCandles;
        self.count    = 0;
        self.duration = durationOfCandle*1000000;
        self.quotes    = list();
        self.candle   = CandleStick();
        self.starttime= -1;

    def update(self, trade):
        if self.starttime == -1:
            self.starttime = trade.txid;

        if ((trade.txid >= self.starttime) and (trade.txid < (self.starttime+self.duration))) :
            self.candle.update(trade);
            return False;
        elif (trade.txid >= (self.starttime+self.duration)) :
            self.quotes.append(self.candle);
            self.count = self.count + 1;
            if len(self.quotes) > self.maxListLen :
                self.quotes.pop(0);
            # print str(self.count)+". Candle: "+str(self.candle);
            self.candle     = CandleStick();
            self.candle.update(trade);
            self.starttime  = self.starttime + self.duration;
            return True;
    def draw(self, buyOrders, sellOrders, indicatorList):
        fig, ax = plt.subplots();
        width = 0.7 * (self.quotes[-1].last - self.quotes[0].last) / len(self.quotes);
        colorup='g';
        colordown='r';
        alpha=0.6;

        OFFSET = width/2.0

        for q in self.quotes:

            if q.close>=q.open :
                color = colorup
                lower = q.open
                height = q.close-q.open
            else           :
                color = colordown
                lower = q.close
                height = q.open-q.close

            vline = Line2D(
                xdata=(q.last, q.last), ydata=(q.low, q.high),
                color=color,
                linewidth=0.5,
                antialiased=True,
                )

            rect = Rectangle(
                xy    = (q.last-OFFSET, lower),
                width = width,
                height = height,
                facecolor = color,
                edgecolor = color,
                )
            rect.set_alpha(alpha)


            #lines.append(vline)
            #patches.append(rect)
            ax.add_line(vline)
            ax.add_patch(rect)
        ax.autoscale_view()

        #plt.setp( plt.gca().get_xticklabels(), rotation=45, horizontalalignment='right')
        for i in range(0, len(buyOrders)) :
            plt.plot(buyOrders[i][1], buyOrders[i][0],"b^");

        for i in range(0, len(sellOrders)) :
            plt.plot(sellOrders[i][1], sellOrders[i][0],"kv");

       # for indicator in indicatorList :
        #    indicator.draw(plt);

        plt.show();



fastMa      = Ma(1);
slowMa      = Ma(24);

starttime = 1353264000
duration  = 86400*200

#ticker  = mtgoxTicker("USD",1);
ticker  = sqliteTicker("USD", starttime, duration);

trade = ticker.getLatest();
broker  = Account(1,0,0.994, trade);

maxPrice    = 0;
minPrice    = 1000000.0;
inBTC       = True;

chart = CandleStickChart(999999, 86400);

while trade is not None:

    if chart.update(trade) == True :
        fastMa.update(chart.quotes[-1].close);
        slowMa.update(chart.quotes[-1].close);

        #print "fastMa: ",fastMa.get()," slowMa: ",slowMa.get()

        if ((fastMa.get() is not None) and (slowMa.get() is not None)) :
            if fastMa.get() > slowMa.get() :
                broker.buy(trade);

            if fastMa.get() < slowMa.get() :
                # Debug me!!!!
                if( (trade.last > (broker.lastOrder.last*1.10)) ) :#
                #if (trade.last < (lastOrder.last*0.50)) :
                    broker.sell(trade);


    # get trade for next loop iteration
    trade = ticker.getLatest();

print("SALDO: BTC ",broker.btc," FIAT ",broker.fiat);
chart.draw(broker.buyOrders, broker.sellOrders, [fastMa, slowMa]);