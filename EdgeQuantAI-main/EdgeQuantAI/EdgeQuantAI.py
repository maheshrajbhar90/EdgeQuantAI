
import pandas as pd
import yfinance as yf
import talib
import warnings
warnings.filterwarnings("ignore")
import os
import sys
import textwrap

# Ensure the directory of the current script is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Now try the import
try:
    from fundamental_analyzer import FundamentalAnalyser
except ImportError:
    from fundamental_analyser import FundamentalAnalyser




class StockTechnicalAnalyzer:

    """
    Full technical analysis engine:
    - Indicators
    - Candlestick patterns
    - Stock scanning
    """

    def __init__(self, period="5y", interval="1d",exchange_suffix=".NS",fmp_api_key=None, openai_key=None):
        self.fundamental = FundamentalAnalyser(
            fmp_api_key=fmp_api_key,
            openai_key=openai_key
        )
        self.period = period
        self.interval = interval
        self.exchange_suffix = exchange_suffix

    # =====================================================
    # 📌 DATA FETCH
    # =====================================================
    def fetch_ohlc(self, ticker):
        df = yf.download(
            ticker + self.exchange_suffix,
            period=self.period,
            interval=self.interval,
            auto_adjust=True,
            progress=False
        )

        if df.empty:
            return None

        df = df.droplevel(level=1, axis=1)
        df = df.reset_index()

        if "Datetime" in df.columns:
            df = df.rename(columns={"Datetime": "Date"})

        df["Date"] = (
            pd.to_datetime(df["Date"], utc=True)
            .dt.tz_convert("Asia/Kolkata")
            .dt.tz_localize(None)
        )

        df = df.set_index("Date")
        df["Ticker"] = ticker
        return df

    def support_resistance_level(self, ohlc_day):
        """Returns pivot point and S/R levels using classic formulas."""
        high = float(ohlc_day["High"].iloc[-1])
        low = float(ohlc_day["Low"].iloc[-1])
        close = float(ohlc_day["Close"].iloc[-1])
        pivot = (high + low + close) / 3
        r1 = (2 * pivot) - low
        r2 = pivot + (high - low)
        r3 = high + 2 * (pivot - low)

        s1 = (2 * pivot) - high
        s2 = pivot - (high - low)
        s3 = low - 2 * (high - pivot)

        return (round(pivot, 2),round(r1, 2),round(r2, 2), round(r3, 2),round(s1, 2),round(s2, 2),round(s3, 2))
        # ---------------- Direction Columns ----------------

    # Bollinger Bands direction
    def bb_direction(self,row):
        if pd.isna(row['bb_upper']) or pd.isna(row['bb_middle']) or pd.isna(row['bb_lower']):
            return 'Neutral'
        if row['Close'] > row['bb_middle']:
            if row['Close'] >= row['bb_upper']:
                return 'Strong Bullish'
            return 'Bullish'
        else:
            if row['Close'] <= row['bb_lower']:
                return 'Strong Bearish'
            return 'Bearish'


    def z_score(self,df,window=20):

      """
      Calculate rolling volume Z-score.
      df must contain a 'Volume' column.
      window = rolling period for mean & std.
      """
      df=df.copy()
      df['vol_mean']=df['Volume'].rolling(window).mean()
      df['vol_std']=df['Volume'].rolling(window).std()
      df['vol_zscore']=(df['Volume']-df['vol_mean'])/df['vol_std']
      return df


    # Stochastic direction
    def stoch_direction(self,row):
        if pd.isna(row['Stoch_k']) or pd.isna(row['stoch_d']):
            return 'Neutral'
        if row['Stoch_k'] > row['stoch_d']:
            if row['Stoch_k'] > 80:
                return 'Overbought Bullish'
            return 'Bullish'
        else:
            if row['Stoch_k'] < 20:
                return 'Oversold Bearish'
            return 'Bearish'


    # ATR direction - volatility measure: increasing ATR implies rising volatility (could mean trend strengthening)

    # ADX direction - strength of trend: ADX > 25 is considered strong trend, otherwise weak trend
    def adx_direction(self,val):
        if pd.isna(val):
            return 'Neutral'
        elif val > 25:
            return 'Strong Trend'
        else:
            return 'Weak Trend'




    # =====================================================
    # 📌 INDICATORS
    # =====================================================

    def add_indicators(self, ohlc):
        data = ohlc.copy()

        if data.empty:
            return None
        if len(data) < 200:
            return None

        close = data["Close"]
        volume = data["Volume"]

        data["VMA20"] = talib.SMA(volume, 20)
        data["EMA5"] = talib.EMA(close, 5)
        data["EMA9"] = talib.EMA(close, 9)
        data["EMA26"] = talib.EMA(close, 26)
        data["SMA50"] = talib.SMA(close, 50)
        data["SMA200"] = talib.SMA(close, 200)

        data["RSI"] = talib.RSI(close, 14)
        data["MACD"], data["Signal"], _ = talib.MACD(close, 12, 26, 9)

        data["bb_upper"], data["bb_middle"], data["bb_lower"] = talib.BBANDS(close, 20)
        data["Stoch_k"], data["stoch_d"] = talib.STOCH(
            data["High"], data["Low"], close
        )

        data["ATR"] = talib.ATR(data["High"], data["Low"], close, 14)
        data["ADX"] = talib.ADX(data["High"], data["Low"], close, 14)
        data["Change"] = close.pct_change()

        data["Z_score"] = self.z_score(data)["vol_zscore"]
        #     # ---- Z-score (safe) ----
        # z_df = self.z_score(data)
        # data["Z_score"] = z_df["vol_zscore"]
        data["BB_Direction"] = data.apply(self.bb_direction, axis=1)
        data["Stoch_Direction"] = data.apply(self.stoch_direction, axis=1)
        data["ATR_Direction"] = data["ATR"].diff().apply(
            lambda x: "Increasing" if x > 0 else "Decreasing"
        )
        data["ADX_Direction"] = data["ADX"].apply(self.adx_direction)

        return data

    def generate_signal(self, data):
        if data is None or len(data) < 2:
            return None

        last = data.iloc[-1]
        prev = data.iloc[-2]

        # ---------------- Support / Resistance ----------------
        pivot, r1, r2, r3, s1, s2, s3 = self.support_resistance_level(last.to_frame().T)

        # ---------------- Conditions ----------------
        cond_volume = last["Volume"] > last["VMA20"]

        # EMA crossover
        bullish_cross = prev["EMA9"] < prev["EMA26"] and last["EMA9"] > last["EMA26"]
        bearish_cross = prev["EMA9"] > prev["EMA26"] and last["EMA9"] < last["EMA26"]
        ema_cross_type = "Bullish" if bullish_cross else "Bearish" if bearish_cross else ""

        # RSI
        cond_rsi = last["RSI"] >= 60

        # MACD crossover
        macd_bullish = prev["MACD"] < prev["Signal"] and last["MACD"] > last["Signal"]
        macd_bearish = prev["MACD"] > prev["Signal"] and last["MACD"] < last["Signal"]
        macd_cross_type = "Bullish" if macd_bullish else "Bearish" if macd_bearish else ""

        # Final filter
        cond_any = cond_volume or bullish_cross or bearish_cross or cond_rsi or macd_bullish or macd_bearish

        if cond_any:

            # ---------------- Final Output ----------------
            return {
                "Date": last.name,
                "Ticker": last["Ticker"],
                "Close": last["Close"],
                "Change%": last["Change"],
                "Volume": last["Volume"],
                "VMA20": last["VMA20"],

                # 🔥 Your missing fields (now included)
                "RSI_Value": last["RSI"],
                "RSI>=60": cond_rsi,
                "MACD_Value": last["MACD"],
                "Signal_Value": last["Signal"],
                "MACD_Crossover": macd_cross_type,
                "Volume_Spike": cond_volume,
                "Z_score":last['Z_score'],

                "BB_Direction": last["BB_Direction"],
                "Stoch_Direction": last["Stoch_Direction"],
                "ATR_Direction": last["ATR_Direction"],
                "ADX_Direction": last["ADX_Direction"],

                # EMA / MA
                "EMA5": last["EMA5"],
                "EMA9": last["EMA9"],
                "EMA26": last["EMA26"],
                "SMA50": last["SMA50"],
                "SMA200": last["SMA200"],
                "EMA_Crossover": ema_cross_type,

                # Support / Resistance
                "Pivot_point": pivot,
                "Resistance_1": r1,
                "Resistance_2": r2,
                "Resistance_3": r3,
                "Support_1": s1,
                "Support_2": s2,
                "Support_3": s3,
            }
        return None

    def identify_candlestick_patterns(self,ohlc_df):
        """
        Detects all candlestick patterns using TA-Lib and adds them as columns in the DataFrame.

        Args:
            ohlc_df (pd.DataFrame): OHLC data as a DataFrame (must include 'Open', 'High', 'Low', 'Close').

        Returns:
            pd.DataFrame: DataFrame with additional columns for each detected candlestick pattern.
        """
        # Dictionary to store the pattern names and corresponding TA-Lib functions
        pattern_functions = {
            "3_inside": talib.CDL3INSIDE,
            "3_line_strike": talib.CDL3LINESTRIKE,
            "3_stars_in_south": talib.CDL3STARSINSOUTH,
            "3_white_soldiers": talib.CDL3WHITESOLDIERS,
            "abandoned_baby": talib.CDLABANDONEDBABY,
            "advance_block": talib.CDLADVANCEBLOCK,
            "belthold": talib.CDLBELTHOLD,
            "breakaway": talib.CDLBREAKAWAY,
            "closing_marubozu": talib.CDLCLOSINGMARUBOZU,
            "conceal_baby_wall": talib.CDLCONCEALBABYSWALL,
            "counter_attack": talib.CDLCOUNTERATTACK,
            "doji": talib.CDLDOJI,
            "doji_star": talib.CDLDOJISTAR,
            "dragonfly_doji": talib.CDLDRAGONFLYDOJI,
            "engulfing": talib.CDLENGULFING,
            "hammer": talib.CDLHAMMER,
            "harami": talib.CDLHARAMI,
            "harami_cross": talib.CDLHARAMICROSS,
            "homing_pigeon": talib.CDLHOMINGPIGEON,
            "inverted_hammer": talib.CDLINVERTEDHAMMER,
            "kicking": talib.CDLKICKING,
            "kicking_by_length": talib.CDLKICKINGBYLENGTH,
            "ladder_bottom": talib.CDLLADDERBOTTOM,
            "matching_low": talib.CDLMATCHINGLOW,
            "morning_doji_star": talib.CDLMORNINGDOJISTAR,
            "morning_star": talib.CDLMORNINGSTAR,
            "on_neck": talib.CDLONNECK,
            "piercing": talib.CDLPIERCING,
            "rickshaw_man": talib.CDLRICKSHAWMAN,
            "rise_fall_3_methods": talib.CDLRISEFALL3METHODS,
            "separating_lines": talib.CDLSEPARATINGLINES,
            "takuri": talib.CDLTAKURI,
            "tasuki_gap": talib.CDLTASUKIGAP,
            "unique_3_river": talib.CDLUNIQUE3RIVER,
            "2_crows": talib.CDL2CROWS,
            "3_black_crows": talib.CDL3BLACKCROWS,
            "3_outside": talib.CDL3OUTSIDE,
            "dark_cloud_cover": talib.CDLDARKCLOUDCOVER,
            "evening_doji_star": talib.CDLEVENINGDOJISTAR,
            "evening_star": talib.CDLEVENINGSTAR,
            "gap_side_side_white": talib.CDLGAPSIDESIDEWHITE,
            "gravestone_doji": talib.CDLGRAVESTONEDOJI,
            "hanging_man": talib.CDLHANGINGMAN,
            "high_wave": talib.CDLHIGHWAVE,
            "hikkake": talib.CDLHIKKAKE,
            "hikkake_mod": talib.CDLHIKKAKEMOD,
            "identical_3_crows": talib.CDLIDENTICAL3CROWS,
            "in_neck": talib.CDLINNECK,
            "ladder_bottom": talib.CDLLADDERBOTTOM,
            "long_legged_doji": talib.CDLLONGLEGGEDDOJI,
            "long_line": talib.CDLLONGLINE,
            "marubozu": talib.CDLMARUBOZU,
            "mathold": talib.CDLMATHOLD,
            "on_neck": talib.CDLONNECK,
            "piercing": talib.CDLPIERCING,
            "rickshaw_man": talib.CDLRICKSHAWMAN,
            "rise_fall_3_methods": talib.CDLRISEFALL3METHODS,
            "separating_lines": talib.CDLSEPARATINGLINES,
            "shooting_star": talib.CDLSHOOTINGSTAR,
            "short_line": talib.CDLSHORTLINE,
            "spinning_top": talib.CDLSPINNINGTOP,
            "stalled_pattern": talib.CDLSTALLEDPATTERN,
            "sticks_and_sandwich": talib.CDLSTICKSANDWICH,
            "thrusting": talib.CDLTHRUSTING,
            "tristar": talib.CDLTRISTAR,
            "upside_gap_2_crows": talib.CDLUPSIDEGAP2CROWS,
            "xside_gap_3_methods": talib.CDLXSIDEGAP3METHODS
            }

        # Iterate through the pattern functions and apply each one
        for pattern_name, pattern_func in pattern_functions.items():
            pattern = pattern_func(ohlc_df['Open'], ohlc_df['High'], ohlc_df['Low'], ohlc_df['Close'])
            if (pattern!=0).any():
                ohlc_df.loc[pattern != 0, 'Pattern'] = pattern_name
                ohlc_df.loc[pattern != 0, 'Code'] = pattern[pattern != 0]
        return ohlc_df


    def get_latest_candlestick_patterns(self,symbols,periods=None,interval=None):
        periods = periods or self.period
        intervals = interval or self.interval
        result_df = []
        pattern_df=[]

        try:

            for tick in symbols:
                ohlc_df = yf.download(tick + self.exchange_suffix,period=periods, interval=intervals, auto_adjust=True)
                # ohlc_df now has DatetimeIndex
                ohlc_df=ohlc_df.droplevel(level=1,axis=1)
                # ohlc_df=ohlc_df.iloc[:-1] ## removes the last row (today’s candle)

                if isinstance(ohlc_df.index, pd.DatetimeIndex) or'Datetime' in ohlc_df.columns:
                    ohlc_df=ohlc_df.reset_index()
                if 'Datetime' in ohlc_df.columns:
                    ohlc_df = ohlc_df.rename(columns={'Datetime': 'Date'})
                elif 'index' in ohlc_df.columns:
                    ohlc_df = ohlc_df.rename(columns={'index': 'Date'})

                ohlc_df = ohlc_df.rename(columns={'Datetime': 'Date'})
                ohlc_df["Date"] = (pd.to_datetime(ohlc_df["Date"], utc=True).dt.tz_convert("Asia/Kolkata").dt.tz_localize(None))
                ohlc_df=ohlc_df.set_index("Date")


                ohlc_df['Ticker']=tick # Now ohlc_df has 'Ticker' column, Date as index
                print(f"Success for {tick}")

                # Identify candlestick patterns
                # Pass a copy to identify_candlestick_patterns to avoid modifying the ohlc_df that analyze_stock uses (which expects index)
                df_with_indicators = self.add_indicators(ohlc_df)
                if df_with_indicators is None:
                    continue   # skip this ticker cleanly
                res_analysis = self.generate_signal(df_with_indicators)
                # result_for_patterns = self.identify_candlestick_patterns(ohlc_df.copy())
                # latest_candle_patterns = result_for_patterns.iloc[-1:, :].copy()
                result_for_patterns = self.identify_candlestick_patterns(df_with_indicators.copy())
                latest_candle_patterns = result_for_patterns.iloc[-1:].reset_index()
                # latest_candle_patterns = latest_candle_patterns.reset_index() # Convert Date index to Date column

                # res_analysis = self.analyze_stock(ohlc_df) # Pass original ohlc_df with Date index

                # print(res_analysis)

                if res_analysis:
                    pattern_df.append(res_analysis)
                    # pattern_df.append(res_analysis) # res_analysis contains 'Date' as a key, 'Ticker' as a key

                # Append the processed latest_candle_patterns
                result_df.append(latest_candle_patterns)

        except Exception as e:
                print(f"An error occurred: {e}")



        # Combine results into a single DataFrame
        final_result_df = pd.concat(result_df, ignore_index=True)
        final_pattern_df = pd.DataFrame(pattern_df)

        if final_result_df.empty or final_pattern_df.empty:
            print("No data to merge. This could be due to errors in analyze_stock or no patterns found.")
            return None

        # Ensure Date formats match - this should now work
        final_pattern_df["Date"] = pd.to_datetime(final_pattern_df["Date"])
        final_result_df["Date"] = pd.to_datetime(final_result_df["Date"])

        # # ---------------- Correct Merge ----------------
        combined_df = pd.merge(final_pattern_df,final_result_df[["Date", "Pattern", "Code", "Ticker"]],
            on=["Date", "Ticker"], how="left")
        return combined_df

    def main(self,ticker:list):

        columns_order = [
        'Date','Ticker','Close','Change%','Volume','VMA20','Z_score','Volume_Spike','EMA5','EMA9','EMA26','SMA50','SMA200',
        'EMA_Crossover','Pivot_point','Resistance_1','Resistance_2','Resistance_3','Support_1','Support_2','Support_3',
        'RSI_Value','RSI>=60','MACD_Value','Signal_Value','MACD_Crossover',
        'BB_Direction','Stoch_Direction','ATR_Direction','ADX_Direction','Pattern','Code']


        ##################################***Main_File***###############################################

        # combined_tickers=list(dict.fromkeys(nifty_50+nifty_100+mid_cap100))

        # Get latest candlestick patterns for Nifty 50 symbols
        final_result = self.get_latest_candlestick_patterns(ticker)
        if final_result is not None: # Add this check

            # final_result=final_result[columns_order]
            final_result = final_result.reindex(columns=columns_order)

            final_result=final_result.round(2)
            # final_result=final_result.sort_values(by='Z_score',ascending=False)
            # print("Success")
        else:
            print("No valid data to process after fetching candlestick patterns. Check the console for errors and ensure `analyze_stock` is functioning correctly.")

        return final_result

    def get_tech_data_for_ticker(self, df, ticker):
        """
        Extract the most recent technical row for the given ticker.
        Returns a dictionary usable in generate_technical_prompt().
        """
        # df.columns = (df.columns.str.replace("\n", " ").str.replace("\r", " ").str.strip())
        # df.columns = (
        # df.columns
        # .str.replace(r"[\n\r]+", " ", regex=True)
        # .str.strip()
        # )

        # Filter DF
        data = df[df['Ticker'] == ticker]

        if data.empty:
            raise ValueError(f"No data found for ticker: {ticker}")

        # Get latest row (last date)
        row = data.iloc[-1]

        # Convert row to dictionary
        tech_data = row.to_dict()

        return tech_data

    

    def generate_technical_prompt(self, ticker, tech_data,mode="simple"):
        
        """
        Same prompt generator you provided, unchanged.
        """

        clean_data = {k: v for k, v in tech_data.items() if v is not None}

        metrics_text = "\n".join([f"     {key}: {value}" for key, value in clean_data.items()])
        # metrics_text = ""
        # for key, value in clean_data.items():
        #     metrics_text += f"{key}: {value}\n"
        # print(metrics_text)

        prompt_1 = textwrap.dedent(f"""
        You are an expert Technical Analyst specializing in stock chart analysis for Indian equities.

        Analyze the stock **{ticker}** using the technical indicators provided below.
        Focus on price action, trend structure, indicators, candlestick patterns,support–resistance
        levels, volume behavior and indicator confluence.

        --You ARE allowed to include recent news, earnings, guidance, or company performance
        ONLY if it directly impacts the short-term technical outlook (momentum, volume, trend strength).

        You MAY include fundamentals ONLY if they directly influence short-term price
        action, such as:
        - Recent earnings (EPS beat/miss, margins, revenue trends)
        - Management guidance
        - Major company events (buybacks, dividends, splits, promoter activity)
        - FPI/DII flows, block/bulk deals
        - Order wins or regulatory announcements affecting momentum or volatility

        DO NOT use long-term fundamentals (ROE, ROCE, PE, Balance Sheet, etc.).
        DO NOT include macroeconomic commentary unrelated to price action.

        ----------------------------------------
        ### Technical Data Provided:
        {metrics_text}
        ----------------------------------------

        ### Your Task:

        1. **Trend Analysis**
        - Evaluate short-term trend (EMA/SMA 5, 10, 20)
        - Evaluate medium-term trend (EMA/SMA 50)
        - Evaluate long-term trend (EMA/SMA 200)
        - Identify higher-high / higher-low or lower-high / lower-low structure
        - Decide if the stock is in an uptrend, downtrend, or consolidation

        2. **Momentum Analysis**
        - Interpret RSI (overbought/oversold/neutral)
        - Analyze MACD direction + crossover
        - Interpret Stochastic.
        - Identify signs of momentum strength or exhaustion

        3. **Volume & Volatility**
        - Check for abnormal volume using Z-score
        - Identify volume spikes and whether they confirm or weaken the move
        - Analyze ATR direction (volatility rising or falling)

        4. **Candlestick Pattern Analysis**
        - Identify reversal or continuation patterns
        - Evaluate pattern strength
        - Confirm with volume when possible

        5. **Support & Resistance**
        - Identify nearest support levels
        - Identify nearest resistance levels
        - Determine if price is testing, rejecting, or breaking these zones

        6. **Entry / Exit Decision**
        Provide:
        - A clear BUY / SELL / HOLD recommendation
        - A suggested entry price (if applicable)
        - A technical stop-loss level
        - Short-term and medium-term targets
        7. **Key Reasoning** (2-3 bullet points maximum):
        - [Primary reason for recommendation]
        - [Supporting factor]
        - [Risk consideration]
        ----------------------------------------
        ### Requirements:
        - Base your judgment mainly on the technical metrics supplied.
        - You MAY include short-term news only when it influences momentum or price reaction.
        - The final answer MUST contain a clear BUY / SELL / HOLD rating with justification.
        ----------------------------------------

        Now generate your full technical analysis.
        """).strip()
        prompt_2=textwrap.dedent(f"""

        You are an expert Technical Analyst. Analyze **{ticker}** using this systematic framework:

        ----------------------------------------
            ### Technical Data Provided:
            {metrics_text}
        ----------------------------------------

        ### PHASE 1: INDICATOR ASSESSMENT (Assign Individual Scores)
        For each category, score as Bullish (+1), Neutral (0), or Bearish (-1):

        1. **Trend Score** (Short/Medium/Long EMA/SMA alignment)
        2. **Momentum Score** (RSI, MACD, Stochastic combined)
        3. **Volume Score** (Z-score, volume spike, trend confirmation)
        4. **Volatility Score** (ATR direction, BB squeeze/expansion)
        5. **Support/Resistance Score** (Price position relative to key levels)

        **Total Technical Score**: Sum all scores (Range: -5 to +5)

        ### PHASE 2: CONFLUENCE CHECK
        - How many indicators point in the same direction?
        - Are there critical contradictions? (e.g., bullish trend but bearish divergence)
        - Which signals are most reliable given current market structure?

        ### PHASE 3: ENTRY CRITERIA VALIDATION
        A valid BUY signal requires:
        - ✓ Technical Score ≥ +3
        - ✓ Volume confirmation (Z-score > 1.5 OR volume spike = True)
        - ✓ Price above key support OR near bounce zone
        - ✓ Risk-reward ratio ≥ 1:2

        If any criterion fails, explain why and suggest HOLD or WAIT.

        ### PHASE 4: RISK-REWARD CALCULATION
        - **Entry Price**: [Specify based on current setup]
        - **Stop-Loss**: [Based on ATR or key support - maximum 3-5% risk]
        - **Target 1**: [Conservative - nearest resistance]
        - **Target 2**: [Aggressive - extended resistance]
        - **Risk-Reward Ratio**: [Calculate explicitly]
        - **Position Size**: [Based on volatility - lower size if ATR increasing]

        ### PHASE 5: CONTEXTUAL FACTORS
        - **Recent News/Events** (Only if directly impacts short-term price action)
        - **Pattern Strength**: Evaluate candlestick pattern reliability
        - **Market Structure**: Is this a breakout, pullback, or reversal setup?

        ### PHASE 6: FINAL DECISION (Use This Exact Format)

        **RECOMMENDATION**: [STRONG BUY / BUY / HOLD / SELL]
        **CONFIDENCE LEVEL**: [HIGH / MEDIUM / LOW]
        **TECHNICAL SCORE**: [X/5]

        **Entry Strategy**:
        - Primary Entry: [Price]
        - Alternative Entry: [Better price if available]

        **Exit Strategy**:
        - Stop-Loss: [Price] (X% risk)
        - Target 1: [Price] - Exit 50% position
        - Target 2: [Price] - Exit remaining 50%
        - Trailing Stop: [Activate when price reaches X%]

        **Trade Invalidation**: [Conditions that void this setup]

        **Key Reasoning** (2-3 bullet points maximum):
        - [Primary reason for recommendation]
        - [Supporting factor]
        - [Risk consideration]

        ### RULES:
        - Never recommend BUY if risk-reward < 1:1.5
        - If indicators conflict (score between -1 to +2), recommend HOLD
        - Cite specific data points from the provided metrics
        - Keep final reasoning concise and actionable

        """).strip()
        if mode == "scoring":
            print(prompt_2)
            return prompt_2
        print(prompt_1)
        return prompt_1


    def build_prompt(self,df, ticker):
        """
        Combines everything:
        - Reads the technical row
        - Generates the LLM prompt
        - Returns a final prompt string
        """
        tech_data = self.get_tech_data_for_ticker(df, ticker)
        tech_prompt=self.generate_technical_prompt(ticker, tech_data)

        return tech_prompt














