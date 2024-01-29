# importはモジュールなどを使用するための記述
# 「import モジュール名」でモジュールをまるごと読み込む。
# 「from モジュール名 import 関数名」でモジュールから指定した関数のみ読み込む。複数のモジュールに同じ名前の関数があるとimportした際にエラーになってしまうため、注意が必要。
import pdb
import time # 定期的にプログラムを動作するためのtime.sleep(sleep関数)を使うため、モジュールをimport。
import pandas as pd # Pandasは、データ解析を容易にする機能を提供するPythonのデータ解析ライブラリ。ポリジャーバンドの計算に使用する。asで別名で使用ができる。
from binance.client import Client # BinanceのAPIを扱うためのライブラリのimport。
import requests # HTTP通信でLINE NotifyのAPIを叩くために使用。
import math #positionの端数を切り捨てる場合に使用。
import os
from dotenv import load_dotenv

# 環境変数ファイルの読み込み
load_dotenv('.env')

# BinanceAPI用変数宣言
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.environ.get("BINANCE_SECRET_KEY")
binance = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY, {"timeout": None}) # バイナンスAPIを処理するクライアントのオブジェクトを、APIキーとSECRETキーを使用して生成。

# LINE NotifyAPI用変数宣言
LINE_NOTIFY_API = os.environ.get("LINE_NOTIFY_API")
LINE_NOTIFY_TOKEN = os.environ.get("LINE_NOTIFY_TOKEN")
LINE_NOTIFY_ERROR_TOKEN = os.environ.get("LINE_NOTIFY_ERROR_TOKEN")

# ロジック用変数宣言
ticker = 'BTC'                         # 取引購入したい銘柄
currency = 'DAI'                      # 取引支払に使う銘柄
interval = 60*5                        # チャート足（60*1 は 1分足）。while文を繰り返す間隔を秒数で指定
duration = 20                          # 移動平均サイズ。何回過去のデータを取得するか。
trading_amount = 50                    # 一回の購入で取引する金額（ドル）
symbol = ticker + currency             # 取引する通貨ペア

file_name = os.path.basename(__file__) #自身のファイル名。例外処理発生時のメッセージ送付に使用

#DataFrameとは、行（raw）と列（column）からなる表。
df = pd.DataFrame() # 簡易的なDBのような入れ物を作成。ここに、価格情報やボリンジャーバンドの情報を入れる。

def get_ex_rate(history): # 関数呼び出し時の引数に「binance.get_my_trades(symbol=symbol)」を渡すことで、過去の取引履歴を渡している。
    history.reverse() # 取引履歴をソートを反転し、降順にする。
    # for でリストをサーチして、一番最後に購入（isBuyerがTrue）した時の価格を拾って返している。
    # range()は、連続する整数のリストを自動で生成する関数。
    # len()は引数のオブジェクトの長さや要素の数を取得する関数。変数historyの要素の数が引数に渡される。
    for i in range(len(history)):
        if history[i]['isBuyer'] == True:
            return float(history[i]['price'])

# LINE Notifyで通知するための関数
def send_line_notify(notification_message):
    headers = {'Authorization': f'Bearer {LINE_NOTIFY_TOKEN}'}
    data = {'message': f'message: {notification_message}'}
    requests.post(LINE_NOTIFY_API, headers = headers, data = data)

def send_line_notify_error(notification_message):
    headers = {'Authorization': f'Bearer {LINE_NOTIFY_ERROR_TOKEN}'}
    data = {'message': f'message: {notification_message}'}
    requests.post(LINE_NOTIFY_API, headers = headers, data = data)

try:
    while True: #while文は条件式がtrueの間、実行され続ける(無限ループ)。Trueを直接渡すことで処理を永遠に繰り返させることができる。
        time.sleep(interval) #繰り返す時間間隔を指定する。

        ticker_info = binance.get_ticker(symbol=symbol) #ティッカーの現在の情報を、API経由で取得
        df = pd.concat([df, pd.DataFrame({'price': [float(ticker_info['lastPrice'])]})], ignore_index=True) #dataframeにpriceというcolumnを作成し、lastplice(直近価格)の値を格納する。「ignore_index」は値格納時、indexに付与された番号を無視するための記述(indexの番号情報は不要なため)。

        if len(df) < duration: # len(df) の条件判断は、移動平均を計算できる長さ（duration）に価格情報が貯まるまで、先に進まないようにしている。
            continue

        # 移動平均を計算できる長さ（duration）に価格情報が貯まったら、以下の処理に進める。
        # ポリジャーバンドの上限と下限を計算している。
        df['SMA'] = df['price'].rolling(window=duration).mean()
        df['std'] = df['price'].rolling(window=duration).std()
        df['-2sigma'] = df['SMA'] - 2*df['std']
        df['+2sigma'] = df['SMA'] + 2*df['std']

        ticker_balance = binance.get_asset_balance(asset=ticker) # 自身の保有している銘柄の口座情報をAPI経由で取得
        position = float(ticker_balance['free']) #1行上で取得した情報から、銘柄の口座残高を取得
        position = math.floor(position * 10 ** 1) / (10 ** 1) # 売却ができる桁数まで切り捨て 

        if position: # position（保有資産）がある時は購入、ないときは売却
            history = binance.get_my_trades(symbol=symbol) # 過去の取引履歴をAPI経由で取得

            # 自動売却するためのif文
            # 条件は「最新価格が、ボリンジャーバンドより上振れたか？」かつ「最新価格が、購入時レート（取引履歴のhistoryからget_ex_rateで取得）より高いか？」とき売却する
            if df['price'].iloc[9] > df['+2sigma'].iloc[-1] \
                    and get_ex_rate(history) < df['price'].iloc[-1]:

                # 売却するための処理
                binance.order_market_sell(symbol=symbol, quantity=position) # 保有している銘柄をすべて売却する
                message = 'sell ' + str(position) + ticker + ' @' + ticker_info['lastPrice'] # 売却時にメッセージを出力
                send_line_notify(message) # LINE Notifyで通知

        else: # positionが存在しない(口座残高がない)とき実行
            if df['price'].iloc[9] < df['-2sigma'].iloc[-1]:
                amount = trading_amount / float(ticker_info['lastPrice']) # 購入する数量を、trading_amount( 一回の売買で取引する金額（ドル）)から計算する
                amount = math.floor(amount * 10 ** 1) / (10 ** 1) # 購入ができる桁数まで切り捨て

                binance.order_market_buy(symbol=symbol, quantity=amount) # 保有している銘柄を購入する
                message = 'buy ' + str(amount) + ticker + ' @' + ticker_info['lastPrice'] # 購入時にメッセージを出力
                send_line_notify(message) # LINE Notifyで通知

        # 価格情報とボリンジャーバンドを入れているdataframeの更新をする
        # 一番古い情報を一つ消して上書きする。メモリを一つズラして上書きするイメージ。
        df = df.iloc[1:, :]
except Exception as e:
    send_line_notify_error(file_name +'が終了されました。\n' + str(e)) # LINE Notifyで通知