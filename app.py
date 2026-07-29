import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import yfinance as yf
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

matplotlib.use("QtAgg")


def download_prices(tickers: tuple[str, ...], period: str) -> pd.DataFrame:
    raw = yf.download(
        list(tickers),
        period=period,
        auto_adjust=True,
        progress=False,
        group_by="column",
    )
    if raw.empty:
        return pd.DataFrame()
    prices = raw["Close"] if "Close" in raw else raw
    if isinstance(prices, pd.Series):
        prices = prices.to_frame(name=tickers[0])
    return prices.dropna(axis=1, how="all").ffill().dropna()


def make_pair_table(correlation: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for index, left in enumerate(correlation.columns):
        for right in correlation.columns[index + 1 :]:
            value = float(correlation.loc[left, right])
            label = (
                "高度同向"
                if value >= 0.7
                else "中度同向"
                if value >= 0.4
                else "低相關"
                if value > -0.4
                else "反向"
            )
            rows.append((left, right, value, label))
    return pd.DataFrame(
        rows, columns=["股票 A", "股票 B", "相關係數", "判讀"]
    ).sort_values("相關係數", ascending=False)


class WorkerSignals(QObject):
    completed = Signal(object, object, object)
    failed = Signal(str)


class AnalysisWorker(QRunnable):
    def __init__(self, tickers: tuple[str, ...], period: str):
        super().__init__()
        self.tickers = tickers
        self.period = period
        self.signals = WorkerSignals()

    def run(self):
        try:
            prices = download_prices(self.tickers, self.period)
            if prices.shape[1] < 2:
                raise ValueError("有效股票不足兩檔，請檢查股票代號。")
            returns = prices.pct_change(fill_method=None).dropna()
            correlation = returns.corr(method="pearson")
            pairs = make_pair_table(correlation)
            self.signals.completed.emit(prices, correlation, pairs)
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class ChartCanvas(FigureCanvasQTAgg):
    def __init__(self):
        self.figure = Figure(facecolor="#111827", tight_layout=True)
        super().__init__(self.figure)

    def show_heatmap(self, correlation: pd.DataFrame):
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        axis.set_facecolor("#111827")
        image = axis.imshow(correlation, cmap="RdBu_r", vmin=-1, vmax=1)
        labels = list(correlation.columns)
        axis.set_xticks(range(len(labels)), labels, rotation=35, ha="right")
        axis.set_yticks(range(len(labels)), labels)
        axis.tick_params(colors="#d1d5db")
        for row in range(len(labels)):
            for column in range(len(labels)):
                value = correlation.iloc[row, column]
                axis.text(
                    column,
                    row,
                    f"{value:.2f}",
                    ha="center",
                    va="center",
                    color="white" if abs(value) > 0.55 else "#111827",
                    fontsize=9,
                )
        colorbar = self.figure.colorbar(image, ax=axis, shrink=0.82)
        colorbar.ax.tick_params(colors="#d1d5db")
        axis.set_title("日報酬率相關矩陣", color="white", fontsize=14, pad=16)
        self.draw()

    def show_prices(self, prices: pd.DataFrame):
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        axis.set_facecolor("#111827")
        normalized = prices.div(prices.iloc[0]).mul(100)
        for column in normalized:
            axis.plot(normalized.index, normalized[column], label=column, linewidth=1.8)
        axis.grid(color="#374151", alpha=0.45)
        axis.tick_params(colors="#d1d5db")
        for spine in axis.spines.values():
            spine.set_color("#374151")
        legend = axis.legend(facecolor="#1f2937", edgecolor="#374151")
        for text in legend.get_texts():
            text.set_color("white")
        axis.set_title("標準化價格走勢（起點 = 100）", color="white", fontsize=14)
        self.draw()


class MetricCard(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("metricCard")
        layout = QVBoxLayout(self)
        title_label = QLabel(title)
        title_label.setObjectName("metricTitle")
        self.value = QLabel("—")
        self.value.setObjectName("metricValue")
        layout.addWidget(title_label)
        layout.addWidget(self.value)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("投資組合相關性分析")
        self.resize(1180, 760)
        self.thread_pool = QThreadPool.globalInstance()
        self.pairs = pd.DataFrame()
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(300)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(24, 28, 24, 24)
        logo = QLabel("CORRELATION\nLAB")
        logo.setObjectName("logo")
        side.addWidget(logo)
        side.addSpacing(30)

        side.addWidget(QLabel("股票代號"))
        self.symbols = QLineEdit("AAPL, MSFT, NVDA, JPM, XOM")
        self.symbols.setPlaceholderText("例如 2330.TW, 2317.TW")
        side.addWidget(self.symbols)
        hint = QLabel("以逗號分隔；台股請加 .TW")
        hint.setObjectName("hint")
        side.addWidget(hint)
        side.addSpacing(18)

        side.addWidget(QLabel("歷史期間"))
        self.period = QComboBox()
        self.period.addItems(["6 個月", "1 年", "2 年", "5 年"])
        self.period.setCurrentIndex(2)
        side.addWidget(self.period)
        side.addSpacing(18)

        self.threshold_label = QLabel("高相關警戒值　0.70")
        side.addWidget(self.threshold_label)
        self.threshold = QSlider(Qt.Horizontal)
        self.threshold.setRange(50, 95)
        self.threshold.setValue(70)
        self.threshold.valueChanged.connect(
            lambda value: self.threshold_label.setText(
                f"高相關警戒值　{value / 100:.2f}"
            )
        )
        side.addWidget(self.threshold)
        side.addSpacing(20)

        self.analyze_button = QPushButton("開始分析")
        self.analyze_button.setObjectName("primaryButton")
        self.analyze_button.clicked.connect(self.start_analysis)
        side.addWidget(self.analyze_button)
        self.export_button = QPushButton("匯出 CSV")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_csv)
        side.addWidget(self.export_button)
        side.addStretch()
        disclaimer = QLabel("資料來自 Yahoo Finance\n僅供分析，不構成投資建議")
        disclaimer.setObjectName("hint")
        side.addWidget(disclaimer)
        outer.addWidget(sidebar)

        content = QWidget()
        main = QVBoxLayout(content)
        main.setContentsMargins(30, 26, 30, 24)
        title = QLabel("投資組合健康檢查")
        title.setObjectName("pageTitle")
        main.addWidget(title)
        subtitle = QLabel("找出看似分散、實際上卻經常一起漲跌的持股")
        subtitle.setObjectName("subtitle")
        main.addWidget(subtitle)

        cards = QGridLayout()
        self.stock_card = MetricCard("有效股票")
        self.average_card = MetricCard("平均兩兩相關")
        self.warning_card = MetricCard("高相關配對")
        cards.addWidget(self.stock_card, 0, 0)
        cards.addWidget(self.average_card, 0, 1)
        cards.addWidget(self.warning_card, 0, 2)
        main.addLayout(cards)

        self.status = QLabel("輸入至少兩檔股票，開始檢查分散效果。")
        self.status.setObjectName("status")
        main.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        main.addWidget(self.progress)

        tabs = QTabWidget()
        self.heatmap = ChartCanvas()
        self.price_chart = ChartCanvas()
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tabs.addTab(self.heatmap, "相關矩陣")
        tabs.addTab(self.table, "股票配對")
        tabs.addTab(self.price_chart, "價格走勢")
        main.addWidget(tabs, 1)
        outer.addWidget(content, 1)

    def start_analysis(self):
        tickers = tuple(
            dict.fromkeys(
                item.strip().upper()
                for item in self.symbols.text().replace("\n", ",").split(",")
                if item.strip()
            )
        )
        if len(tickers) < 2:
            QMessageBox.warning(self, "資料不足", "請輸入至少兩個不同股票代號。")
            return
        periods = ["6mo", "1y", "2y", "5y"]
        self.analyze_button.setEnabled(False)
        self.progress.show()
        self.status.setText("正在下載行情並計算相關性…")
        worker = AnalysisWorker(tickers, periods[self.period.currentIndex()])
        worker.signals.completed.connect(self.show_results)
        worker.signals.failed.connect(self.show_error)
        self.thread_pool.start(worker)

    def show_results(
        self, prices: pd.DataFrame, correlation: pd.DataFrame, pairs: pd.DataFrame
    ):
        self.progress.hide()
        self.analyze_button.setEnabled(True)
        self.export_button.setEnabled(True)
        self.pairs = pairs
        threshold = self.threshold.value() / 100
        high_count = int((pairs["相關係數"] >= threshold).sum())
        mask = ~np.eye(len(correlation), dtype=bool)
        mean_value = float(correlation.where(mask).stack().mean())
        self.stock_card.value.setText(f"{prices.shape[1]} 檔")
        self.average_card.value.setText(f"{mean_value:.2f}")
        self.warning_card.value.setText(f"{high_count} 組")
        if high_count:
            self.status.setText(
                f"發現 {high_count} 組高度同向持股，增加檔數不一定等於分散風險。"
            )
            self.status.setProperty("warning", True)
        else:
            self.status.setText("目前沒有超過警戒值的配對，歷史分散效果較佳。")
            self.status.setProperty("warning", False)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.heatmap.show_heatmap(correlation)
        self.price_chart.show_prices(prices)
        self.fill_table(pairs, threshold)

    def fill_table(self, pairs: pd.DataFrame, threshold: float):
        self.table.setRowCount(len(pairs))
        self.table.setColumnCount(len(pairs.columns))
        self.table.setHorizontalHeaderLabels(list(pairs.columns))
        for row, values in enumerate(pairs.itertuples(index=False)):
            for column, value in enumerate(values):
                text = f"{value:.3f}" if column == 2 else str(value)
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                if column == 2 and float(value) >= threshold:
                    item.setForeground(QColor("#fb7185"))
                    item.setFont(QFont("", weight=QFont.Bold))
                self.table.setItem(row, column, item)

    def show_error(self, message: str):
        self.progress.hide()
        self.analyze_button.setEnabled(True)
        self.status.setText("分析失敗，請檢查股票代號與網路連線。")
        QMessageBox.critical(self, "分析失敗", message)

    def export_csv(self):
        default = str(Path.home() / "stock_correlation_pairs.csv")
        path, _ = QFileDialog.getSaveFileName(
            self, "儲存分析結果", default, "CSV 檔案 (*.csv)"
        )
        if path:
            self.pairs.to_csv(path, index=False, encoding="utf-8-sig")
            QMessageBox.information(self, "匯出完成", f"已儲存至：\n{path}")


STYLESHEET = """
QWidget { background: #111827; color: #e5e7eb; font-family: "Microsoft JhengHei UI"; font-size: 14px; }
#sidebar { background: #0b1220; border-right: 1px solid #253047; }
#logo { color: #60a5fa; font-size: 23px; font-weight: 800; letter-spacing: 2px; }
#pageTitle { font-size: 28px; font-weight: 800; color: white; }
#subtitle, #hint { color: #94a3b8; font-size: 12px; }
QLineEdit, QComboBox { background: #182235; border: 1px solid #334155; border-radius: 7px; padding: 10px; }
QPushButton { background: #1f2937; border: 1px solid #334155; border-radius: 7px; padding: 10px; font-weight: 600; }
QPushButton:hover { background: #293548; }
QPushButton:disabled { color: #64748b; }
#primaryButton { background: #2563eb; border: none; color: white; }
#primaryButton:hover { background: #3b82f6; }
#metricCard { background: #182235; border: 1px solid #293548; border-radius: 10px; margin-top: 16px; }
#metricTitle { color: #94a3b8; font-size: 12px; }
#metricValue { color: white; font-size: 24px; font-weight: 800; }
#status { background: #12253d; color: #7dd3fc; border-radius: 7px; padding: 10px; margin-top: 8px; }
#status[warning="true"] { background: #3a2029; color: #fda4af; }
QTabWidget::pane { border: 1px solid #293548; border-radius: 7px; }
QTabBar::tab { background: #182235; padding: 10px 20px; margin-right: 3px; }
QTabBar::tab:selected { background: #2563eb; color: white; }
QTableWidget { background: #111827; alternate-background-color: #182235; gridline-color: #293548; }
QHeaderView::section { background: #1f2937; color: #cbd5e1; padding: 9px; border: none; }
QProgressBar { border: none; background: #1f2937; height: 5px; }
QProgressBar::chunk { background: #3b82f6; }
"""


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
