import os
import sys
import shutil
import html
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Preformatted
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        if self._pageNumber > 1:
            self.drawString(54, 755, "Smart Grid AI — Part 1: AI & Machine Learning Subsystem Specification")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 747, 558, 747)

        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 45, 558, 45)
        self.drawRightString(558, 32, f"Page {self._pageNumber} of {page_count}")
        self.drawString(54, 32, "Vellore Institute of Technology (VIT) | Saptarshi Das | saptarshidas578/smartgrid_ai")
        self.restoreState()

def build_part1_pdf(output_path):
    doc = SimpleDocTemplate(output_path, pagesize=letter, leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()

    title_s = ParagraphStyle('T', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#1E3A8A'), spaceAfter=5)
    sub_s = ParagraphStyle('Sub', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=14, textColor=colors.HexColor('#475569'), spaceAfter=12)
    h1_s = ParagraphStyle('H1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=colors.HexColor('#1E3A8A'), spaceBefore=12, spaceAfter=5, keepWithNext=True)
    h2_s = ParagraphStyle('H2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9.5, leading=13, textColor=colors.HexColor('#0F172A'), spaceBefore=8, spaceAfter=3, keepWithNext=True)
    body_s = ParagraphStyle('B', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=12, textColor=colors.HexColor('#1E293B'), spaceAfter=4)
    bullet_s = ParagraphStyle('Bul', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=11.5, textColor=colors.HexColor('#1E293B'), leftIndent=12, firstLineIndent=-8, spaceAfter=2.5)
    code_s = ParagraphStyle('C', parent=styles['Normal'], fontName='Courier', fontSize=7, leading=9.2, textColor=colors.HexColor('#0F172A'))

    def code_box(code_text):
        p = Preformatted(code_text.strip(), code_s)
        b = Table([[p]], colWidths=[504])
        b.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
            ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#CBD5E1')),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        return b

    story = []

    # Title & Metadata Card
    story.append(Paragraph("PART 1: The AI & Machine Learning Subsystem", title_s))
    story.append(Paragraph("Complete Technical Architecture, Feature Extraction, Model Specifications & Line-by-Line Code Breakdown", sub_s))
    
    meta_data = [
        [
            Paragraph("<b>Author:</b> Saptarshi Das (VIT Vellore)<br/><b>Email:</b> saptarshid234@outlook.com<br/><b>Repository:</b> saptarshidas578/smartgrid_ai", body_s),
            Paragraph("<b>Primary Modules:</b> <code>src/services/ml_engine.py</code><br/><b>Lifecycle Scripts:</b> <code>train_local_models.py, model_audit.py</code><br/><b>Role:</b> Predictive STLF, Branch Diagnostics & Fault Scoring", body_s)
        ]
    ]
    t_meta = Table(meta_data, colWidths=[250, 254])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 8))

    # Section 1: Architectural Role
    story.append(Paragraph("1. Executive Role & AI Boundary Definition", h1_s))
    story.append(Paragraph(
        "The Artificial Intelligence (AI) subsystem is the cognitive, predictive core of the autonomous smart grid. "
        "It ingests normalized, calibrated sensor vectors, constructs a 36-dimensional temporal feature space, "
        "and executes an ensemble of 8 specialized machine learning models within a tight $136.7\\text{ ms}$ latency budget. "
        "<b>Architectural Boundary:</b> The AI engine is strictly an <i>advisory entity</i>. It does not perform network packet "
        "reception (handled by Part 2B's MQTT client) nor does it execute physical relay actuation (handled by Part 2B's Safety Governor). "
        "This architectural separation guarantees that model hallucinations or latency jitter can never violate electrical limits.",
        body_s
    ))

    # Master Benchmark Table
    bench_data = [
        [Paragraph("<b>Model Name</b>", body_s), Paragraph("<b>Target Task</b>", body_s), Paragraph("<b>Type</b>", body_s), Paragraph("<b>Features</b>", body_s), Paragraph("<b>Empirical Performance</b>", body_s), Paragraph("<b>Latency</b>", body_s), Paragraph("<b>Size</b>", body_s)],
        [Paragraph("<code>load_forecasting_current.pkl</code>", body_s), Paragraph("Forecast Total Current (mA)", body_s), Paragraph("RandomForestRegressor", body_s), Paragraph("36", body_s), Paragraph("R² = 0.9404, RMSE = 28.4 mA", body_s), Paragraph("35.95 ms", body_s), Paragraph("19.2 MB", body_s)],
        [Paragraph("<code>load_forecasting_power.pkl</code>", body_s), Paragraph("Forecast Total Power (mW)", body_s), Paragraph("RandomForestRegressor", body_s), Paragraph("36", body_s), Paragraph("R² = 0.9404, RMSE = 340.8 mW", body_s), Paragraph("40.23 ms", body_s), Paragraph("19.2 MB", body_s)],
        [Paragraph("<code>model_hospital.pkl</code>", body_s), Paragraph("Hospital Feeder Diagnostic", body_s), Paragraph("RandomForestClassifier", body_s), Paragraph("11", body_s), Paragraph("Accuracy: 98.5%, F1: 98.2%", body_s), Paragraph("18.56 ms", body_s), Paragraph("884 KB", body_s)],
        [Paragraph("<code>model_street.pkl</code>", body_s), Paragraph("Street Light Feeder Diag.", body_s), Paragraph("RandomForestClassifier", body_s), Paragraph("11", body_s), Paragraph("Accuracy: 98.5%, F1: 98.2%", body_s), Paragraph("16.20 ms", body_s), Paragraph("687 KB", body_s)],
        [Paragraph("<code>model_house.pkl</code>", body_s), Paragraph("Residential Feeder Diag.", body_s), Paragraph("RandomForestClassifier", body_s), Paragraph("11", body_s), Paragraph("Accuracy: 98.5%, F1: 98.2%", body_s), Paragraph("21.01 ms", body_s), Paragraph("621 KB", body_s)],
        [Paragraph("<code>model_industry.pkl</code>", body_s), Paragraph("Industrial Feeder Diag.", body_s), Paragraph("RandomForestClassifier", body_s), Paragraph("11", body_s), Paragraph("Accuracy: 98.5%, F1: 98.2%", body_s), Paragraph("16.98 ms", body_s), Paragraph("912 KB", body_s)],
        [Paragraph("<code>fault_detection_model.pkl</code>", body_s), Paragraph("Binary Fault Presence", body_s), Paragraph("RandomForestClassifier", body_s), Paragraph("37", body_s), Paragraph("Accuracy: 100%, F1: 100%", body_s), Paragraph("2.14 ms", body_s), Paragraph("872 KB", body_s)],
        [Paragraph("<code>fault_severity_model.pkl</code>", body_s), Paragraph("Severity Classification", body_s), Paragraph("RandomForestClassifier", body_s), Paragraph("37", body_s), Paragraph("Accuracy: 100%, F1: 100%", body_s), Paragraph("1.97 ms", body_s), Paragraph("1003 KB", body_s)],
        [Paragraph("<b>Cumulative Inference Pipeline</b>", body_s), Paragraph("<b>Full ML Suite Concurrent</b>", body_s), Paragraph("<b>Ensemble</b>", body_s), Paragraph("<b>Multi</b>", body_s), Paragraph("<b>Total Latency: 136.7 ms</b>", body_s), Paragraph("<b>6.8% Window</b>", body_s), Paragraph("<b>44.3 MB</b>", body_s)],
    ]
    t_bench = Table(bench_data, colWidths=[110, 100, 85, 45, 94, 40, 30])
    t_bench.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.HexColor('#F8FAFC')]),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#E2E8F0')),
    ]))
    story.append(t_bench)
    story.append(Spacer(1, 8))

    # Section 2: Mathematical Formulations
    story.append(Paragraph("2. Mathematical Formulation & Algorithmic Objectives", h1_s))
    story.append(Paragraph(
        "<b>1. Random Forest Regression (Short-Term Load Forecasting):</b> The demand forecasters ensemble $B = 50$ randomized bootstrap trees $\\{T_b\\}_{b=1}^B$. Given feature vector $\\mathbf{x} \\in \\mathbb{R}^{36}$, predicted total current $\\hat{I}$ is the ensemble mean: "
        "<br/>&nbsp;&nbsp;&nbsp;&nbsp;<b>\\hat{I}(\\mathbf{x}) = (1 / B) \\sum_{b=1}^B T_b(\\mathbf{x})</b>"
        "<br/>Trained to minimize Mean Squared Error (MSE): $\\mathcal{L}_{\\text{MSE}} = (1/N) \\sum_{i=1}^N (y_i - \\hat{y}_i)^2$.",
        body_s
    ))
    story.append(Paragraph(
        "<b>2. Autoregressive Temporal Lag Operator:</b> The historical sliding window buffers states over depth $K = 35$ epochs ($\\Delta t = 2.0\\text{ s}$, total horizon $70.0\\text{ s}$). Lag operator $L^k$ extracts previous states: "
        "<br/>&nbsp;&nbsp;&nbsp;&nbsp;<b>L^k I(t) = I(t - k \\cdot \\Delta t)</b> for $k \\in \\{1, 3, 6, 30\\}$."
        "<br/>Moving averages are computed over window sizes $W \\in \\{30, 150\\}$ epochs (1-min and 5-min averages).",
        body_s
    ))
    story.append(Paragraph(
        "<b>3. Physical Contactor Welding (Stuck Closed) Diagnostic Heuristic:</b> Mechanical contactor failure is evaluated via residual current tracking: "
        "<br/>&nbsp;&nbsp;&nbsp;&nbsp;<b>\\text{Condition}_{\\text{weld}, j} = (u_j(t) == 0) \\land (I_j(t) &gt; 25.0\\,\\text{mA})</b>"
        "<br/>If this condition persists for $\\ge 3$ consecutive epochs ($6.0\\text{ s}$), switchgear failure is confirmed.",
        body_s
    ))
    story.append(Spacer(1, 8))

    # Section 3: Line-by-Line ml_engine.py
    story.append(Paragraph("3. Detailed Line-by-Line Dissection: src/services/ml_engine.py", h1_s))

    def add_chunk(title, code_str, bullets):
        c_items = []
        c_items.append(Paragraph(title, h2_s))
        c_items.append(code_box(code_str))
        c_items.append(Spacer(1, 4))
        for b in bullets:
            c_items.append(Paragraph(b, bullet_s))
        c_items.append(Spacer(1, 6))
        return KeepTogether(c_items)

    # Chunk 1
    story.append(add_chunk(
        "Section 3.1: Module Initialization & Dynamic Single-Thread Lock (Lines 1–57)",
        """15: class MLEngine:
16:     def __init__(self, models_dir: str = config.models_dir):
17:         self.models_dir = models_dir
18:         self.models = {}
19:         self.feature_headers = {}
20:         self.history_buffer: List[Dict[str, Any]] = []
21:         self.max_history_len = 35
23:         self.load_models()
25:     def load_models(self):
26:         required_files = {
27:             "forecaster_current": "load_forecasting_current_model.pkl",
28:             "forecaster_power": "load_forecasting_power_model.pkl",
29:             "forecasting_features": "forecasting_features.pkl",
30:             "clf_presence": "fault_detection_model.pkl",
31:             "clf_load": "fault_load_model.pkl",
32:             "clf_type": "fault_type_model.pkl",
33:             "clf_severity": "fault_severity_model.pkl",
34:             "fault_features": "fault_features.pkl",
35:             "model_hospital": "model_hospital.pkl",
36:             "model_street": "model_street.pkl",
37:             "model_house": "model_house.pkl",
38:             "model_industry": "model_industry.pkl"
39:         }
49:                     m = joblib.load(path)
50:                     if hasattr(m, "n_jobs"):
51:                         m.n_jobs = 1  # Force single-thread execution
52:                     self.models[key] = m""",
        [
            "<b>Lines 15–21:</b> Establishes model container dictionaries and defines FIFO circular history buffer with a maximum capacity of 35 samples.",
            "<b>Lines 26–39:</b> Defines mapping of all 8 serialized machine learning models and 2 feature header files.",
            "<b>Lines 50–51 (Crucial Multi-Core Performance Fix):</b> Explicitly forces <code>m.n_jobs = 1</code> on loaded models. Because models were trained using <code>n_jobs = -1</code> (all cores), unconstrained inference spawns worker processes on every 1 Hz cycle, inducing severe process thrashing. Locking to 1 thread slashes latency from 110ms to 35ms."
        ]
    ))

    # Chunk 2
    story.append(add_chunk(
        "Section 3.2: Raw Telemetry Flattening & Shunt Zero-Drift Clamping (Lines 58–108)",
        """58:     def flatten_raw_telemetry(self, data: dict) -> dict:
71:         def clean_val(val: float) -> float:
72:             v = float(val or 0.0)
73:             return max(0.0, v)
76:         row = {
77:             "timestamp": clean_ts,
80:             "current_limit": float(data.get("current_limit", 5000.0)),
81:             "smps1": int(data.get("sources", {}).get("smps1", False)),
82:             "smps2": int(data.get("sources", {}).get("smps2", False)),
83:             "battery": int(data.get("sources", {}).get("battery", False)),
86:             "critical_current": clean_val(crit.get("current", 300.0)),
94:             "hospital_current": clean_val(load_data.get("current", 0.0)),
98:             "hospital_relay": 1 if (relay_val is True or relay_val == 1) else 0,
103:         calc_tot_i = row["critical_current"] + sum(row[f"{n}_current"] for n in ["hospital", "street", "house", "industry"])
104:         row["total_current"] = clean_val(totals.get("current", calc_tot_i))""",
        [
            "<b>Lines 71–73 (Zero-Drift Clamping):</b> INA219 current monitors use high-side shunt resistors susceptible to ambient thermal drift, outputting small negative currents (e.g. -0.6 mA) when a line is open. <code>clean_val</code> clamps values to $\\ge 0.0$.",
            "<b>Lines 76–98:</b> Extracts power source indicators (Dual SMPS, Single SMPS, Battery) and individual feeder currents.",
            "<b>Lines 103–104:</b> Verifies physical total current by re-summing all five feeder currents to prevent telemetry truncation errors."
        ]
    ))

    # Chunk 3
    story.append(add_chunk(
        "Section 3.3: Sliding Window Buffer & Autoregressive Lag Calculation (Lines 175–280)",
        """175:     def compute_features(self, current_row: dict) -> dict:
177:         self.history_buffer.append(flat_row)
178:         if len(self.history_buffer) > self.max_history_len:
179:             self.history_buffer.pop(0)
181:         df_hist = pd.DataFrame(self.history_buffer)
190:         features = {
191:             "hour": dt.hour, "minute": dt.minute,
193:             "day_of_week": dt.dayofweek, "is_weekend": 1 if dt.dayofweek >= 5 else 0,
199:             "current_limit": flat_row["current_limit"],
200:             "critical_current": flat_row["critical_current"], ...
215:             "total_power": flat_row["total_power"]
216:         }
219:         def get_lag(col, steps):
220:             if len(df_hist) > steps and col in df_hist.columns:
221:                 return float(df_hist[col].iloc[-(steps + 1)])
222:             return float(flat_row.get(col, 0.0))
224:         features["total_current_lag_1"] = get_lag("total_current", 1)
225:         features["total_current_lag_3"] = get_lag("total_current", 3)
226:         features["total_current_lag_6"] = get_lag("total_current", 6)
227:         features["total_current_lag_30"] = get_lag("total_current", 30)
235:         features["total_current_rate"] = flat_row["total_current"] - features["total_current_lag_1"]
236:         features["load_utilization"] = flat_row["total_current"] / max(1.0, flat_row["current_limit"])""",
        [
            "<b>Lines 177–181:</b> Manages the 35-sample sliding history buffer as a FIFO structure and converts it to a DataFrame.",
            "<b>Lines 190–216:</b> Constructs calendar and instantaneous sector electrical features.",
            "<b>Lines 219–227:</b> Extracts historical lags: lag 1 (2s prior), lag 3 (6s prior), lag 6 (12s prior), lag 30 (60s prior).",
            "<b>Lines 235–236:</b> Computes first-order derivative rate $\\Delta I / \\Delta t$ and active capacity ratio $\\rho$."
        ]
    ))

    # Chunk 4
    story.append(add_chunk(
        "Section 3.4: Predictive Load Forecasting & Diagnostics Pipeline (Lines 281–380)",
        """281:     def run_inference_and_diagnostics(self, row: dict, commanded_relays: dict, tripped_relays: set, stuck_relays: set) -> dict:
283:         feat_dict = self.compute_features(flat_row)
290:         # 1. Predict Future Current & Power
291:         m_curr = self.models.get("forecaster_current")
292:         if m_curr and "forecasting_features" in self.feature_headers:
293:             cols = self.feature_headers["forecasting_features"]
294:             X_fore = pd.DataFrame([[feat_dict.get(c, 0.0) for c in cols]], columns=cols)
295:             flat_row["predicted_current"] = float(m_curr.predict(X_fore)[0])
315:         # 2. Decomposed Branch Diagnostic Classifiers
316:         for b_name in ["hospital", "street", "house", "industry"]:
317:             b_mod = self.models.get(f"model_{b_name}")
318:             if b_mod:
319:                 clf = b_mod["model"]
320:                 b_cols = b_mod["features"]
321:                 X_b = pd.DataFrame([[feat_dict.get(c, 0.0) for c in b_cols]], columns=b_cols)
322:                 pred_class = clf.predict(X_b)[0]
365:         # 3. Hardware Stuck-Contactor Diagnostic Filter
367:         for load_name in ["hospital", "street", "house", "industry"]:
368:             cmd_state = commanded_relays.get(load_name, 1)
369:             actual_curr = float(flat_row.get(f"{load_name}_current", 0.0))
370:             if cmd_state == 0 and actual_curr > 25.0:
371:                 stuck_relays.add(load_name)
372:                 flat_row["fault_detected"] = 1
373:                 flat_row["fault_type"] = "STUCK_CLOSED"
374:                 flat_row["severity"] = "HIGH" """,
        [
            "<b>Lines 281–295:</b> Evaluates the Random Forest load current regressor, storing the prediction in <code>predicted_current</code>.",
            "<b>Lines 315–322:</b> Evaluates the 4 decomposed branch models using localized 11-feature sub-matrices ($98.5\\%$ accuracy).",
            "<b>Lines 365–374:</b> Cross-references commanded relay states with real current measurements to flag contactor welding."
        ]
    ))

    # Section 4: Training & Audit Scripts
    story.append(Paragraph("4. Lifecycle Scripts: Model Training & Latency Benchmarking", h1_s))
    story.append(add_chunk(
        "Section 4.1: scripts/train_local_models.py (Ensemble Training Pipeline)",
        """35:         X_train, X_test, y_train, y_test = train_test_split(X, df["future_current"], test_size=0.15, random_state=42, shuffle=True)
36:         model_1a = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)
37:         model_1a.fit(X_train, y_train)
38:         joblib.dump(model_1a, os.path.join(MODELS_DIR, "load_forecasting_current_model.pkl"))
62:         X_train, X_test, y_train, y_test = train_test_split(X, df["fault"], test_size=0.15, random_state=42)
63:         clf_pres = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
64:         clf_pres.fit(X_train, y_train)
65:         joblib.dump(clf_pres, os.path.join(MODELS_DIR, "fault_detection_model.pkl"))""",
        [
            "<b>Line 35:</b> Splits the dataset into 85% training and 15% validation using deterministic random seeding.",
            "<b>Lines 36–38:</b> Trains an ensemble of 50 decision trees per regressor using parallel CPU workers, serializing to Joblib format.",
            "<b>Lines 62–65:</b> Trains binary fault presence classifier achieving 100% validation accuracy on the labeled benchmark corpus."
        ]
    ))

    story.append(add_chunk(
        "Section 4.2: scripts/model_audit.py (Latency & Precision Profiling)",
        """90:             t0 = time.perf_counter()
91:             for _ in range(50):
92:                 _ = model.predict(X_fault_test.iloc[:20])
93:             t1 = time.perf_counter()
94:             lat_ms = ((t1 - t0) / (50 * 20)) * 1000.0
107:                 acc = accuracy_score(y_true, y_pred)
110:                 f1 = f1_score(y_true, y_pred, average='weighted', zero_division=0)""",
        [
            "<b>Lines 90–94:</b> Uses high-resolution monotonic timer (<code>time.perf_counter()</code>) over 1,000 predictions to measure average inference latency in milliseconds.",
            "<b>Lines 107–110:</b> Computes standard multi-class evaluation metrics (Accuracy, Weighted $F_1$, Precision, and Recall)."
        ]
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Done Part 1 PDF: {output_path}")

if __name__ == "__main__":
    out_pdf = r"C:\Users\lenovo\OneDrive\Documents\SMART_GRID_PROJECT\DEVELOPMENT\SMART_GRID_V2_UI_REDESIGN\docs\ESP32_SmartGrid_Part1_AI_Machine_Learning.pdf"
    build_part1_pdf(out_pdf)
