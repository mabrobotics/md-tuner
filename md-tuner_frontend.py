import customtkinter as ctk
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import pyCandle as pc
import matplotlib.pyplot as plt
import datetime as dt
import csv

from md_tuner_backend import DriveBackend


# ===== MOTOR INIT =====
candle = pc.attachCandle(pc.CANdleDatarate_E.CAN_DATARATE_1M, pc.busTypes_t.USB)
md = pc.MD(100, candle)

err = md.init()
if err != pc.MD_Error_t.OK:
    print("Motor init error:", err)
    exit()


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class PIDTuner(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("PID Drive Tuner")
        self.geometry("1400x820")

        self.running = False
        self.mode = ctk.StringVar(value="Position")

        self.backend = DriveBackend(md)

        self.x = []
        self.y = []
        self.target_data = []

        self.x_buf = []
        self.y_buf = []
        self.t_buf = []

        self.temp_var = ctk.StringVar(value="-- °C")
        self.pos_var = ctk.StringVar(value="-- Nm")

        self.build_layout()
        self.build_plot()

        self.on_mode_change("Position")

        self.after(30, self.refresh_plot_loop)
        self.load_pid_to_ui("Position")
        self.time_offset = 0

    # =========================
    # EXPORT CHART TO PNG/JPG
    # =========================

    def export_chart(self):
        now = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # PNG
        self.fig.savefig(f"chart_{dt.datetime.now()}.png")

        # CSV
        try:
            with open(f"chart_{now}.csv", "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["time", "actual", "target"])

                for i in range(len(self.x)):
                    writer.writerow([
                        self.x[i],
                        self.y[i] if i < len(self.y) else "",
                        self.target_data[i] if i < len(self.target_data) else ""
                    ])

            self.log("Exported CSV + PNG")

        except Exception as e:
            self.error(f"CSV export error: {e}")

    # =========================
    # LOAD PID INTO UI
    # =========================
    def load_pid_to_ui(self, mode):
        kp, ki, kd = self.backend.read_pid(mode)

        if kp is None:
            return

        if mode == "Position":
            self.kp_pos.delete(0, "end")
            self.kp_pos.insert(0, str(kp))

            self.ki_pos.delete(0, "end")
            self.ki_pos.insert(0, str(ki))

            self.kd_pos.delete(0, "end")
            self.kd_pos.insert(0, str(kd))
        else:
            self.kp_vel.delete(0, "end")
            self.kp_vel.insert(0, str(kp))

            self.ki_vel.delete(0, "end")
            self.ki_vel.insert(0, str(ki))

            self.kd_vel.delete(0, "end")
            self.kd_vel.insert(0, str(kd))

        


    # =========================
    # MODE CHANGE
    # =========================
    def on_mode_change(self, choice):
        for f in [self.target_frame, self.duration_frame,
                self.pos_frame, self.vel_frame,
                self.btn_frame, self.temp_row, self.pos_row]:
            f.pack_forget()

        if choice == "Velocity":
            for frame in [self.target_frame, self.duration_frame,
                        self.vel_frame, self.btn_frame,
                        self.temp_row, self.pos_row]:
                frame.pack(fill="x", pady=5)
        else:
            for frame in [self.target_frame, self.duration_frame,
                        self.pos_frame, self.btn_frame,
                        self.temp_row, self.pos_row]:
                frame.pack(fill="x", pady=5)
        self.load_pid_to_ui(choice)

    # =========================
    # SAFE FLOATs
    # =========================
    def safe_float(self, x):
        if isinstance(x, (tuple, list)):
            x = x[0]
        return float(str(x).replace(",", "."))

    def start_test(self):
        if self.running:
            return
        if self.x:
            self.time_offset = self.x[-1]
        else:
            self.time_offset = 0

        try:
            duration = self.safe_float(self.duration.get())
            target = self.safe_float(self.target.get())

            if self.mode.get() == "Position":
                kp = self.safe_float(self.kp_pos.get())
                ki = self.safe_float(self.ki_pos.get())
                kd = self.safe_float(self.kd_pos.get())
            else:
                kp = self.safe_float(self.kp_vel.get())
                ki = self.safe_float(self.ki_vel.get())
                kd = self.safe_float(self.kd_vel.get())

        except:
            self.error("Invalid input")
            return

        self.backend.configure(self.mode.get(), kp, ki, kd)

        self.running = True
        self.log("Test started")

        self.backend.start_test(
            self.mode.get(),
            target,
            duration,
            callback=self.backend_callback
        )

    # =========================
    # BACKEND CALLBACK
    # =========================
    def backend_callback(self, data):

        if "event" in data:
            if data["event"] == "finished":
                self.running = False
                self.log("Finished")
            elif data["event"] == "error":
                self.running = False
                self.error(data["msg"])
            return

        try:
            self.x_buf.append(float(data["time"]) + self.time_offset)
            self.y_buf.append(float(data["actual"]))
            self.t_buf.append(float(data["target"]))
        except:
            pass

    # =========================
    # PLOT LOOP
    # =========================
    def refresh_plot_loop(self):

        if self.x_buf:

            self.x.extend(self.x_buf)
            self.y.extend(self.y_buf)
            self.target_data.extend(self.t_buf)

            self.x_buf.clear()
            self.y_buf.clear()
            self.t_buf.clear()

            self.line_actual.set_data(self.x, self.y)
            self.line_target.set_data(self.x, self.target_data)

            self.ax.relim()
            self.ax.autoscale_view()

            self.canvas.draw()

        # === LIVE STATUS UPDATE ===
        try:
            temp = self.backend.get_temperature()
            pos = self.backend.get_position()

            if temp is not None:
                self.temp_var.set(f"{temp:.1f} °C")

            if pos is not None:
                self.pos_var.set(f"{pos:.2f}")

        except:
            pass

        self.after(30, self.refresh_plot_loop)

    # =========================
    # CONTROL
    # =========================
    def abort_test(self):
        self.backend.stop()
        self.running = False
        self.log("Aborted")

    def reset_test(self):
        self.backend.stop()
        self.running = False

        self.x.clear()
        self.y.clear()
        self.target_data.clear()

        self.line_actual.set_data([], [])
        self.line_target.set_data([], [])

        self.canvas.draw_idle()

        self.logs.delete("1.0", "end")
        self.errors.delete("1.0", "end")

        self.log("Reset")

    # =========================
    # LOGS
    # =========================
    def log(self, t):
        self.logs.insert("end", t + "\n")
        self.logs.see("end")

    def error(self, t):
        self.errors.insert("end", t + "\n")
        self.errors.see("end")

    # =========================
    # UI
    # =========================
    def build_layout(self):

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, width=260)
        left.grid(row=0, column=0, sticky="nsw", padx=10, pady=10)

        ctk.CTkLabel(left, text="PID PARAMETERS",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)

        ctk.CTkOptionMenu(
            left,
            values=["Position", "Velocity"],
            variable=self.mode,
            command=self.on_mode_change,
            fg_color="#747474",
            button_color="#747474",
            button_hover_color="#747474",
            text_color="black"
        ).pack(pady=5)

        self.pos_frame = self.section(left, "Position PID")
        self.kp_pos = self.entry(self.pos_frame, "Kp")
        self.ki_pos = self.entry(self.pos_frame, "Ki")
        self.kd_pos = self.entry(self.pos_frame, "Kd")

        self.vel_frame = self.section(left, "Velocity PID")
        self.kp_vel = self.entry(self.vel_frame, "Kp")
        self.ki_vel = self.entry(self.vel_frame, "Ki")
        self.kd_vel = self.entry(self.vel_frame, "Kd")

        # target
        self.target_frame = self.section(left, "Target")
        self.target = self.entry(self.target_frame, "Value")
        # duration
        self.duration_frame = self.section(left, "Time")
        self.duration = self.entry(self.duration_frame, "Duration")

        # === STATIC CONTAINER (FIX UI JUMP) ===
        self.control_container = ctk.CTkFrame(left)
        self.control_container.pack(fill="x", pady=20)

        # BUTTONS
        self.btn_frame = ctk.CTkFrame(self.control_container)
        self.btn_frame.pack(fill="x")

        ctk.CTkButton(self.btn_frame, text="START", hover_color="#4d4d4d", command=self.start_test).pack(fill="x", pady=5)
        ctk.CTkButton(self.btn_frame, text="ABORT", hover_color="#4d4d4d", command=self.abort_test, fg_color="red").pack(fill="x", pady=5)
        ctk.CTkButton(self.btn_frame, text="RESET", hover_color="#4d4d4d", command=self.reset_test, fg_color="grey").pack(fill="x", pady=5)
        ctk.CTkButton(self.btn_frame, text="SAVE CHART", hover_color="#4d4d4d", command=self.export_chart, fg_color="green").pack(fill="x", pady=5)

        # STATUS PANEL (FIXED POSITION)
        self.status_frame = ctk.CTkFrame(self.control_container, fg_color="#1a1a1a")
        self.status_frame.pack(fill="x", pady=10)

        # Temperature row
        self.temp_row = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        self.temp_row.pack(fill="x", padx=8, pady=4)

        ctk.CTkLabel(self.temp_row, text="Temperature:", text_color="#666666").pack(side="left")

        self.temp_label = ctk.CTkLabel(
            self.temp_row,
            textvariable=self.temp_var,
            text_color="#666666",
            font=ctk.CTkFont(weight="bold")
        )
        self.temp_label.pack(side="right")

        # Position row
        self.pos_row = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        self.pos_row.pack(fill="x", padx=8, pady=4)

        ctk.CTkLabel(self.pos_row, text="Position:", text_color="#666666").pack(side="left")

        self.pos_label = ctk.CTkLabel(
            self.pos_row,
            textvariable=self.pos_var,
            text_color="#666666",
            font=ctk.CTkFont(weight="bold")
        )
        self.pos_label.pack(side="right")

        self.vel_frame.pack_forget()

        center = ctk.CTkFrame(self)
        center.grid(row=0, column=1, sticky="nsew")

        self.pframe = ctk.CTkFrame(center)
        self.pframe.pack(fill="both", expand=True)

        right = ctk.CTkFrame(self)
        right.grid(row=0, column=2, sticky="nse")

        logs_label = ctk.CTkLabel(right, text="LOGS")
        logs_label.pack()

        self.logs = ctk.CTkTextbox(right, height=250)
        self.logs.pack(fill="both", expand=True)

        errors_label = ctk.CTkLabel(right, text="ERRORS")
        errors_label.pack()

        self.errors = ctk.CTkTextbox(right, height=200)
        self.errors.pack(fill="both", expand=True)

    # =========================
    # HELPERS
    # =========================
    def section(self, parent, title):
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", pady=8)

        label = ctk.CTkLabel(frame, text=title,
                             font=ctk.CTkFont(size=14, weight="bold"))
        label.pack(anchor="w", padx=10, pady=5)

        return frame

    def entry(self, parent, text):
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", padx=10, pady=4)

        label = ctk.CTkLabel(frame, text=text, width=120)
        label.pack(side="left")

        entry = ctk.CTkEntry(frame)
        entry.pack(side="right", fill="x", expand=True)

        return entry

    # =========================
    # PLOT
    # =========================
    def build_plot(self):

        self.fig = Figure(figsize=(8, 6.5), facecolor="#1a1a1a")
        self.ax = self.fig.add_subplot(111)

        self.ax.set_facecolor("#1a1a1a")
        self.ax.grid(True)

        self.line_actual, = self.ax.plot([], [], color="#ff0015", label="Actual")
        self.line_target, = self.ax.plot([], [], "--", color="#13e2e2", label="Target")

        self.ax.tick_params(colors="#e6e6e6")
        self.ax.spines["bottom"].set_color("#e6e6e6")
        self.ax.spines["left"].set_color("#e6e6e6")
        self.ax.spines["top"].set_color("#444444")
        self.ax.spines["right"].set_color("#444444")

        self.ax.set_title("Drive Response", color="white")
        self.ax.legend()

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.pframe)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)


if __name__ == "__main__":
    app = PIDTuner()
    app.mainloop()