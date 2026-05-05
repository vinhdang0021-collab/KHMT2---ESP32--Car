import tkinter as tk
from tkinter import scrolledtext
import socket
import threading
import time

BG         = "#0d0d14"   
PANEL      = "#141420"   
PANEL2     = "#1a1a2e"   
BORDER     = "#2a2a45"   
BTN_DARK   = "#1e1e35"  
BTN_HOVER  = "#2a2a50"   

CYAN       = "#00d4ff"   
CYAN_DIM   = "#005566"   
CYAN_GLOW  = "#00ffff"  
GREEN      = "#00ff88"  
GREEN_DIM  = "#003322"   
RED        = "#ff3355"   
RED_DIM    = "#330011"   
ORANGE     = "#ff8800"  
ORANGE_DIM = "#331a00"  
YELLOW     = "#ffdd00"   
YELLOW_DIM = "#332b00"  
PURPLE     = "#aa44ff"  
PURPLE_DIM = "#220033"  
WHITE      = "#e0e8ff"  
GRAY       = "#555577"   
GRAY2      = "#333355"   

FONT_TITLE = ("Courier", 18, "bold")   
FONT_BIG   = ("Courier", 13, "bold")   
FONT_MED   = ("Courier", 10, "bold")   
FONT_SMALL = ("Courier", 9)           
FONT_MONO  = ("Courier", 9)           

sock            = None   
safe_mode_on    = False   
horn_on         = False  
police_on       = False   
headlight_on    = False   
left_signal_on  = False   
right_signal_on = False   
last_distance   = 999    
police_flash_id = None    

def connect():
    """
    Kết nối đến ESP32 qua TCP socket.
    Đọc IP và Port từ ô nhập liệu, rồi thử kết nối trong một thread riêng
    để không làm đơ giao diện trong lúc chờ.
    """
    global sock

    ip       = ip_var.get().strip()
    port_str = port_var.get().strip()

    if not ip or not port_str:
        log("Nhập IP và Port trước!", "danger")
        return

    try:
        port = int(port_str)
    except ValueError:
        log("Port không hợp lệ!", "danger")
        return

    set_conn_status("connecting")
    root.update_idletasks()  

    def do_connect():
        """Hàm chạy trong thread phụ — thực hiện kết nối thực sự"""
        global sock
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)         
            s.connect((ip, port))   
            s.settimeout(None)      
            root.after(0, lambda: set_conn_status("connected", ip, port))
            root.after(0, lambda: log(f"Kết nối thành công → {ip}:{port}", "info"))
            t = threading.Thread(target=receive_loop, daemon=True)
            t.start()

        except Exception as e:
            root.after(0, lambda: set_conn_status("disconnected"))
            root.after(0, lambda: log(f"Lỗi kết nối: {e}", "danger"))
    threading.Thread(target=do_connect, daemon=True).start()

def disconnect():
    """Ngắt kết nối khỏi ESP32 và cập nhật giao diện"""
    global sock

    if sock:
        try:
            sock.close()  
        except:
            pass          
        sock = None        

    set_conn_status("disconnected")
    log("Đã ngắt kết nối.", "info")


def send(cmd):
    """
    Gửi một ký tự lệnh đến ESP32 qua socket.
    Ví dụ: send('F') = tiến, send('S') = dừng
    """
    global sock

    if sock:
        try:
            sock.sendall(cmd.encode())   
        except Exception as e:
            log(f"Lỗi gửi lệnh '{cmd}': {e}", "danger")
            root.after(0, disconnect)    
    else:
        log("Chưa kết nối với xe!", "danger")

def receive_loop():
    """
    Vòng lặp nhận dữ liệu từ ESP32, chạy liên tục trong thread riêng.
    ESP32 gửi dữ liệu dạng text, mỗi tin nhắn kết thúc bằng ký tự xuống dòng \\n.
    """
    buffer = ""   

    while sock:
        try:
            data = sock.recv(1024).decode('utf-8', errors='ignore')

            if not data:
                break   
            buffer += data   
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)   
                line = line.strip()                   
                if not line:
                    continue   
                if line.startswith("DIST:"):
                    val = line.split(":")[1]
                    root.after(0, update_distance, val)

                elif line == "WARN:obstacle":
                    root.after(0, on_obstacle_warning)

                elif line == "WARN:blocked":
                    root.after(0, on_blocked_warning)

                elif line == "WARN:crash":
                    root.after(0, lambda: log("💥 Va chạm phát hiện!", "danger"))

                elif line.startswith("AUTO:"):

                    state = line.split(":")[1]
                    root.after(0, lambda s=state: log(f"Safe Drive: {s}", "info"))

                elif line == "READY":
                    root.after(0, lambda: log("✅ ESP32 sẵn sàng!", "info"))

        except:
            break

    root.after(0, lambda: log("⚠️ Mất kết nối với xe!", "danger"))
    root.after(0, lambda: set_conn_status("disconnected"))

def on_obstacle_warning():
    """Xử lý khi ESP32 báo phát hiện vật cản và đã dừng xe tự động"""
    log("🛑 VẬT CẢN! Xe đã dừng tự động.", "danger")
    dist_canvas.itemconfig(dist_arc, outline=RED)
    flash_warning()

def on_blocked_warning():
    """Xử lý khi lệnh tiến bị chặn do Safe Mode đang bật"""
    log("🚫 Không thể tiến — có vật cản phía trước!", "danger")

def flash_warning():
    """
    Hiệu ứng nháy đỏ-cam trên vòng cung cảm biến để cảnh báo trực quan.
    Dùng root.after() để lên lịch đổi màu theo thời gian (ms).
    """
    dist_canvas.itemconfig(dist_arc, outline=RED)
    root.after(300, lambda: dist_canvas.itemconfig(dist_arc, outline=ORANGE))
    root.after(600, lambda: dist_canvas.itemconfig(dist_arc, outline=RED))
    root.after(900, lambda: dist_canvas.itemconfig(dist_arc, outline=ORANGE))

def update_distance(val):
    """
    Cập nhật hiển thị khoảng cách từ cảm biến siêu âm.
    - Đổi màu theo mức độ nguy hiểm
    - Cập nhật vòng cung tỉ lệ với khoảng cách
    - Chặn nút Tiến nếu Safe Mode bật và quá gần
    """
    global last_distance

    try:
        d = int(val)
        last_distance = d

        dist_value_label.config(text=f"{d}")

        if d <= 20:
            color  = RED
            status = "NGUY HIỂM"
        elif d <= 40:
            color  = ORANGE
            status = "CHÚ Ý"
        elif d < 999:
            color  = GREEN
            status = "AN TOÀN"
        else:
            color  = GRAY
            status = "---"

        dist_value_label.config(fg=color)
        dist_status_label.config(text=status, fg=color)
        dist_canvas.itemconfig(dist_arc, outline=color)

        pct   = min(d, 200) / 200.0  
        angle = int(pct * 270)        
        dist_canvas.itemconfig(dist_arc, extent=-angle)

        if safe_mode_on and d <= 20:
            btn_forward.config(bg=RED_DIM, fg=RED)    
        elif safe_mode_on:
            btn_forward.config(bg=PANEL2, fg=CYAN)   

    except:
        dist_value_label.config(text="?")


def set_conn_status(state, ip="", port=""):
    """
    Cập nhật hiển thị trạng thái kết nối ở góc trên trái.
    state: "connected" | "connecting" | "disconnected"
    """
    if state == "connected":
        conn_dot.config(bg=GREEN)
        conn_label.config(text=f"CONNECTED  {ip}:{port}", fg=GREEN)
        btn_connect.config(
            text="DISCONNECT",
            bg=RED_DIM,
            fg=RED,
            command=disconnect
        )

    elif state == "connecting":
        conn_dot.config(bg=ORANGE)
        conn_label.config(text="CONNECTING...", fg=ORANGE)

    else:  # disconnected
        conn_dot.config(bg=GRAY)
        conn_label.config(text="DISCONNECTED", fg=GRAY)
        btn_connect.config(
            text="CONNECT",
            bg=CYAN_DIM,
            fg=CYAN,
            command=connect
        )


def update_clock():
    """Cập nhật đồng hồ hiển thị ở góc phải tiêu đề, gọi lại mỗi 1 giây"""
    clock_label.config(text=time.strftime("%H:%M:%S"))
    root.after(1000, update_clock)


def log(msg, tag="normal"):
    """
    Ghi một dòng vào hộp log phía dưới bên phải.
    tag: "normal" | "info" | "danger"  — quyết định màu chữ
    """
    timestamp = time.strftime("%H:%M:%S")

    log_box.config(state='normal')                             
    log_box.insert(tk.END, f"[{timestamp}] {msg}\n", tag)     
    log_box.see(tk.END)                                         
    log_box.config(state='disabled')                           

def cmd_forward():
    """
    Gửi lệnh Tiến về phía trước.
    Nếu Safe Mode bật và vật cản <= 20cm thì chặn lại.
    """
    if safe_mode_on and last_distance <= 20 and last_distance > 0:
        log("🚫 Safe Drive: Không thể tiến! Vật cản phía trước.", "danger")
        flash_warning()
        return
    send('F')


def cmd_backward():
    """Gửi lệnh Lùi về phía sau"""
    send('B')


def cmd_left():
    """Gửi lệnh Rẽ trái"""
    send('L')


def cmd_right():
    """Gửi lệnh Rẽ phải"""
    send('R')


def cmd_stop():
    """Gửi lệnh Dừng xe"""
    send('S')


def on_speed(val):
    """
    Được gọi khi người dùng kéo thanh tốc độ.
    Gửi giá trị tốc độ (1-9) dưới dạng chuỗi.
    """
    speed_value = int(float(val))
    send(str(speed_value))


def toggle_headlight():
    """Bật hoặc tắt đèn pha — gửi 'H' để bật, 'h' để tắt"""
    global headlight_on

    headlight_on = not headlight_on  

    if headlight_on:
        send('H')
        btn_headlight.config(bg=YELLOW_DIM, fg=YELLOW, text="💡 ĐÈN PHA\n  ON")
        log("Đèn pha: BẬT", "info")
    else:
        send('h')
        btn_headlight.config(bg=PANEL2, fg=GRAY, text="💡 ĐÈN PHA\n  OFF")
        log("Đèn pha: TẮT", "info")


def toggle_left_signal():
    """Bật hoặc tắt xi nhan trái — gửi 'Q' để bật, 'q' để tắt"""
    global left_signal_on

    left_signal_on = not left_signal_on

    if left_signal_on:
        send('Q')
        btn_left_sig.config(bg=YELLOW_DIM, fg=YELLOW, text="◀◀ XI NHAN\n  TRÁI")
        log("Xi nhan trái: BẬT", "info")
    else:
        send('q')
        btn_left_sig.config(bg=PANEL2, fg=GRAY, text="◀ XI NHAN\n  TRÁI")
        log("Xi nhan trái: TẮT", "info")


def toggle_right_signal():
    """Bật hoặc tắt xi nhan phải — gửi 'E' để bật, 'e' để tắt"""
    global right_signal_on

    right_signal_on = not right_signal_on

    if right_signal_on:
        send('E')
        btn_right_sig.config(bg=YELLOW_DIM, fg=YELLOW, text="XI NHAN ▶▶\n  PHẢI")
        log("Xi nhan phải: BẬT", "info")
    else:
        send('e')
        btn_right_sig.config(bg=PANEL2, fg=GRAY, text="XI NHAN ▶\n  PHẢI")
        log("Xi nhan phải: TẮT", "info")


def toggle_horn():
    """Bật hoặc tắt còi thường — gửi 'Z' để bật, 'z' để tắt"""
    global horn_on

    horn_on = not horn_on

    if horn_on:
        send('Z')
        btn_horn.config(bg=ORANGE_DIM, fg=ORANGE, text="📢 CÒI\n  ON")
        log("Còi: BẬT", "info")
    else:
        send('z')
        btn_horn.config(bg=PANEL2, fg=GRAY, text="📢 CÒI\n  OFF")
        log("Còi: TẮT", "info")


def toggle_police():
    """
    Bật hoặc tắt còi cảnh sát — gửi 'P' để bật, 'p' để tắt.
    Khi bật: khởi động hiệu ứng nháy màu ở thanh tiêu đề.
    Khi tắt: hủy hiệu ứng nháy và khôi phục màu tiêu đề.
    """
    global police_on, police_flash_id

    police_on = not police_on

    if police_on:
        send('P')
        btn_police.config(bg=PURPLE_DIM, fg=PURPLE, text="🚨 CẢNH SÁT\n  ON")
        log("Còi cảnh sát: BẬT", "info")
        police_flash_loop()   # Bắt đầu vòng lặp nháy tiêu đề
    else:
        send('p')
        btn_police.config(bg=PANEL2, fg=GRAY, text="🚨 CẢNH SÁT\n  OFF")
        log("Còi cảnh sát: TẮT", "info")

        if police_flash_id:
            root.after_cancel(police_flash_id)
            police_flash_id = None

        title_bar.config(bg=PANEL)


def police_flash_loop():
    """
    Hiệu ứng nháy đỏ-xanh ở thanh tiêu đề khi còi cảnh sát đang bật.
    Tự gọi lại chính nó mỗi 300ms để tạo vòng lặp vô tận.
    """
    global police_flash_id

    if not police_on:
        return   
    current_color = title_bar.cget("bg")

    if current_color == "#002233":
        next_color = "#220033"
    else:
        next_color = "#002233"

    title_bar.config(bg=next_color)

    police_flash_id = root.after(300, police_flash_loop)


def toggle_safe_mode():
    """
    Bật hoặc tắt Safe Drive Mode.
    Khi bật: gửi 'A', cập nhật nút và đèn chỉ báo ở tiêu đề.
    Khi tắt: gửi 'a', khôi phục màu mặc định.
    """
    global safe_mode_on

    safe_mode_on = not safe_mode_on

    if safe_mode_on:
        send('A')

        btn_safe.config(
            bg="#002211",
            fg=GREEN,
            text="🛡️ SAFE DRIVE\n    ON",
            relief="solid",
            bd=1
        )

        safe_indicator.config(bg=GREEN)

        log("🛡️ Safe Drive Mode: BẬT — Xe tự dừng khi vật cản ≤ 20cm", "info")

    else:
        send('a')
        btn_safe.config(
            bg=PANEL2,
            fg=GRAY,
            text="🛡️ SAFE DRIVE\n    OFF",
            relief="flat",
            bd=0
        )

        safe_indicator.config(bg=GRAY2)

        btn_forward.config(bg=PANEL2, fg=CYAN)

        log("Safe Drive Mode: TẮT", "info")


def key_press(e):
    """
    Xử lý khi người dùng nhấn phím.
    Tra cứu trong bảng ánh xạ phím → hàm tương ứng rồi gọi.
    """
    key_map = {
        'w':     cmd_forward,
        'up':    cmd_forward,
        's':     cmd_backward,
        'down':  cmd_backward,
        'a':     cmd_left,
        'left':  cmd_left,
        'd':     cmd_right,
        'right': cmd_right,
        'space': cmd_stop,
        'h':     toggle_headlight,
        'z':     toggle_horn,
    }

    key = e.keysym.lower()

    fn = key_map.get(key)
    if fn:
        fn()


def key_release(e):
    """
    Xử lý khi người dùng nhả phím di chuyển.
    Tự động gửi lệnh Dừng khi thả phím WASD hoặc phím mũi tên.
    """
    move_keys = {'w', 's', 'a', 'd', 'up', 'down', 'left', 'right'}

    key = e.keysym.lower()

    if key in move_keys:
        send('S')

def make_button(parent, text, command, width=10, height=2, bg=None, fg=None, font=None):
    """
    Tạo một nút bấm với style chung của giao diện.
    Tự động thêm hiệu ứng hover (sáng lên khi rê chuột vào).
    """
    if bg   is None: bg   = PANEL2
    if fg   is None: fg   = CYAN
    if font is None: font = FONT_MED

    btn = tk.Button(
        parent,
        text=text,
        command=command,
        width=width,
        height=height,
        bg=bg,
        fg=fg,
        font=font,
        relief="flat",
        bd=0,
        activebackground=BTN_HOVER,
        activeforeground=WHITE,
        cursor="hand2"
    )

    # Hiệu ứng hover: sáng khi rê vào, tối lại khi rê ra
    def on_enter(event, button=btn, original_bg=bg):
        button.config(bg=BTN_HOVER)

    def on_leave(event, button=btn, original_bg=bg):
        button.config(bg=original_bg)

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)

    return btn

def make_panel(parent, title="", padx=6, pady=6):
    """
    Tạo một panel có viền mỏng và tiêu đề tùy chọn.
    Trả về (frame ngoài, frame trong) để đặt widget vào frame trong.
    """
    outer = tk.Frame(parent, bg=BORDER, padx=1, pady=1)

    inner = tk.Frame(outer, bg=PANEL, padx=padx, pady=pady)
    inner.pack(fill="both", expand=True)

    if title:
        tk.Label(
            inner,
            text=title,
            bg=PANEL,
            fg=GRAY,
            font=FONT_SMALL
        ).pack(anchor="w")

    return outer, inner

root = tk.Tk()
root.title("ESP32 CAR — CONTROL DASHBOARD")
root.geometry("760x860")
root.configure(bg=BG)
root.resizable(False, False)

title_bar = tk.Frame(root, bg=PANEL, pady=10)
title_bar.pack(fill="x")

tk.Label(
    title_bar,
    text="◈ ESP32 RC CAR",
    bg=PANEL,
    fg=CYAN,
    font=FONT_TITLE
).pack(side="left", padx=20)

tk.Label(
    title_bar,
    text="SAFE:",
    bg=PANEL,
    fg=GRAY,
    font=FONT_SMALL
).pack(side="left", padx=(20, 2))

safe_indicator = tk.Label(title_bar, text="●", bg=PANEL, fg=GRAY2, font=FONT_MED)
safe_indicator.pack(side="left")

clock_label = tk.Label(title_bar, text="", bg=PANEL, fg=GRAY, font=FONT_MED)
clock_label.pack(side="right", padx=20)

tk.Frame(root, bg=CYAN, height=1).pack(fill="x")

main = tk.Frame(root, bg=BG)
main.pack(fill="both", expand=True, padx=10, pady=8)

col_left  = tk.Frame(main, bg=BG)
col_right = tk.Frame(main, bg=BG)
col_left.pack(side="left",  fill="both", expand=True, padx=(0, 5))
col_right.pack(side="right", fill="both", expand=True, padx=(5, 0))

p_outer, p_conn = make_panel(col_left, "  CONNECTION")
p_outer.pack(fill="x", pady=(0, 6))

row_ip = tk.Frame(p_conn, bg=PANEL)
row_ip.pack(fill="x", pady=2)

tk.Label(row_ip, text="IP", bg=PANEL, fg=GRAY, font=FONT_SMALL, width=3).pack(side="left")

ip_var = tk.StringVar(value="10.118.79.42")
tk.Entry(
    row_ip,
    textvariable=ip_var,
    width=16,
    bg=PANEL2,
    fg=CYAN,
    insertbackground=CYAN,
    relief="flat",
    font=FONT_MONO,
    highlightthickness=1,
    highlightbackground=BORDER,
    highlightcolor=CYAN
).pack(side="left", padx=4)

tk.Label(row_ip, text="PORT", bg=PANEL, fg=GRAY, font=FONT_SMALL).pack(side="left", padx=(6, 2))

port_var = tk.StringVar(value="8888")
tk.Entry(
    row_ip,
    textvariable=port_var,
    width=6,
    bg=PANEL2,
    fg=CYAN,
    insertbackground=CYAN,
    relief="flat",
    font=FONT_MONO,
    highlightthickness=1,
    highlightbackground=BORDER,
    highlightcolor=CYAN
).pack(side="left", padx=4)

btn_connect = tk.Button(
    row_ip,
    text="CONNECT",
    command=connect,
    bg=CYAN_DIM,
    fg=CYAN,
    font=FONT_MED,
    relief="flat",
    padx=10,
    pady=3,
    cursor="hand2",
    activebackground=BTN_HOVER,
    activeforeground=WHITE
)
btn_connect.pack(side="left", padx=6)

row_status = tk.Frame(p_conn, bg=PANEL)
row_status.pack(fill="x", pady=(2, 0))

conn_dot = tk.Label(row_status, text=" ●", bg=PANEL, fg=GRAY, font=FONT_MED)
conn_dot.pack(side="left")

conn_label = tk.Label(row_status, text="DISCONNECTED", bg=PANEL, fg=GRAY, font=FONT_SMALL)
conn_label.pack(side="left", padx=4)

p_outer2, p_ctrl = make_panel(col_left, "  MOVEMENT CONTROL")
p_outer2.pack(fill="x", pady=6)

ctrl_grid = tk.Frame(p_ctrl, bg=PANEL)
ctrl_grid.pack(pady=4)

btn_forward = make_button(ctrl_grid, "▲\nTIẾN", cmd_forward, width=9, height=2, fg=CYAN)
btn_forward.grid(row=0, column=1, padx=4, pady=4)

make_button(ctrl_grid, "◀  TRÁI", cmd_left, width=9, height=2, fg=CYAN).grid(
    row=1, column=0, padx=4, pady=4
)

btn_stop = tk.Button(
    ctrl_grid,
    text="■\nDỪNG",
    command=cmd_stop,
    width=9,
    height=2,
    bg=RED_DIM,
    fg=RED,
    font=FONT_BIG,
    relief="flat",
    cursor="hand2",
    activebackground=RED,
    activeforeground=WHITE
)
btn_stop.grid(row=1, column=1, padx=4, pady=4)

make_button(ctrl_grid, "PHẢI  ▶", cmd_right, width=9, height=2, fg=CYAN).grid(
    row=1, column=2, padx=4, pady=4
)

make_button(ctrl_grid, "▼\nLÙI", cmd_backward, width=9, height=2, fg=CYAN).grid(
    row=2, column=1, padx=4, pady=4
)

tk.Label(
    p_ctrl,
    text="[ WASD / Arrow Keys = Di chuyển   Space = Dừng ]",
    bg=PANEL,
    fg=GRAY,
    font=FONT_SMALL
).pack(pady=(0, 4))

p_outer3, p_speed = make_panel(col_left, "  SPEED CONTROL")
p_outer3.pack(fill="x", pady=6)

speed_row = tk.Frame(p_speed, bg=PANEL)
speed_row.pack(fill="x")

tk.Label(speed_row, text="MIN", bg=PANEL, fg=GRAY, font=FONT_SMALL).pack(side="left")

speed_var = tk.IntVar(value=7)
spd_scale = tk.Scale(
    speed_row,
    from_=1,
    to=9,
    orient="horizontal",
    variable=speed_var,
    command=on_speed,
    length=220,
    bg=PANEL,
    fg=CYAN,
    highlightthickness=0,
    troughcolor=BORDER,
    sliderrelief="flat",
    activebackground=CYAN,
    showvalue=False
)
spd_scale.pack(side="left", padx=6)

tk.Label(speed_row, text="MAX", bg=PANEL, fg=GRAY, font=FONT_SMALL).pack(side="left")

speed_display = tk.Label(
    speed_row,
    textvariable=speed_var,
    bg=PANEL,
    fg=CYAN,
    font=FONT_BIG,
    width=2
)
speed_display.pack(side="left", padx=10)

p_outer4, p_safe = make_panel(col_left, "  SAFE DRIVE MODE")
p_outer4.pack(fill="x", pady=6)

safe_row = tk.Frame(p_safe, bg=PANEL)
safe_row.pack(fill="x")

btn_safe = tk.Button(
    safe_row,
    text="🛡️ SAFE DRIVE\n    OFF",
    command=toggle_safe_mode,
    width=14,
    height=2,
    bg=PANEL2,
    fg=GRAY,
    font=FONT_MED,
    relief="flat",
    cursor="hand2",
    activebackground=BTN_HOVER,
    activeforeground=WHITE
)
btn_safe.pack(side="left", padx=4, pady=4)

tk.Label(
    safe_row,
    text="Tự động dừng\nkhi vật cản ≤ 20cm\nvà kêu cảnh báo",
    bg=PANEL,
    fg=GRAY,
    font=FONT_SMALL,
    justify="left"
).pack(side="left", padx=12)

p_outer5, p_dist = make_panel(col_right, "  DISTANCE SENSOR")
p_outer5.pack(fill="x", pady=(0, 6))

dist_canvas = tk.Canvas(p_dist, width=120, height=120, bg=PANEL, highlightthickness=0)
dist_canvas.pack(side="left", padx=10, pady=4)

dist_canvas.create_arc(
    10, 10, 110, 110,
    start=-225,
    extent=270,
    style="arc",
    outline=GRAY2,
    width=8
)

dist_arc = dist_canvas.create_arc(
    10, 10, 110, 110,
    start=-225,
    extent=0,
    style="arc",
    outline=GREEN,
    width=8
)

dist_value_label = tk.Label(
    dist_canvas,
    text="---",
    bg=PANEL,
    fg=GREEN,
    font=("Courier", 20, "bold")
)
dist_canvas.create_window(60, 55, window=dist_value_label)
dist_canvas.create_text(60, 82, text="cm", fill=GRAY, font=FONT_SMALL)

dist_info = tk.Frame(p_dist, bg=PANEL)
dist_info.pack(side="left", fill="y", pady=8)

tk.Label(dist_info, text="KHOẢNG CÁCH", bg=PANEL, fg=GRAY, font=FONT_SMALL).pack(anchor="w")

dist_status_label = tk.Label(dist_info, text="---", bg=PANEL, fg=GRAY, font=FONT_BIG)
dist_status_label.pack(anchor="w", pady=4)

tk.Label(dist_info, text="≤ 20cm → DỪNG (safe mode)", bg=PANEL, fg=GRAY2, font=FONT_SMALL).pack(anchor="w")
tk.Label(dist_info, text="≤ 40cm → CHÚ Ý",            bg=PANEL, fg=GRAY2, font=FONT_SMALL).pack(anchor="w")
tk.Label(dist_info, text="  > 40cm → AN TOÀN",         bg=PANEL, fg=GRAY2, font=FONT_SMALL).pack(anchor="w")

p_outer6, p_lights = make_panel(col_right, "  LIGHTS")
p_outer6.pack(fill="x", pady=6)

lights_row = tk.Frame(p_lights, bg=PANEL)
lights_row.pack(fill="x", pady=4)

btn_headlight = tk.Button(
    lights_row,
    text="💡 ĐÈN PHA\n  OFF",
    command=toggle_headlight,
    width=11,
    height=2,
    bg=PANEL2,
    fg=GRAY,
    font=FONT_MED,
    relief="flat",
    cursor="hand2",
    activebackground=BTN_HOVER
)
btn_headlight.pack(side="left", padx=4)

btn_left_sig = tk.Button(
    lights_row,
    text="◀ XI NHAN\n  TRÁI",
    command=toggle_left_signal,
    width=11,
    height=2,
    bg=PANEL2,
    fg=GRAY,
    font=FONT_MED,
    relief="flat",
    cursor="hand2",
    activebackground=BTN_HOVER
)
btn_left_sig.pack(side="left", padx=4)

btn_right_sig = tk.Button(
    lights_row,
    text="XI NHAN ▶\n  PHẢI",
    command=toggle_right_signal,
    width=11,
    height=2,
    bg=PANEL2,
    fg=GRAY,
    font=FONT_MED,
    relief="flat",
    cursor="hand2",
    activebackground=BTN_HOVER
)
btn_right_sig.pack(side="left", padx=4)

p_outer7, p_horn = make_panel(col_right, "  HORN & SIREN")
p_outer7.pack(fill="x", pady=6)

horn_row = tk.Frame(p_horn, bg=PANEL)
horn_row.pack(fill="x", pady=4)

btn_horn = tk.Button(
    horn_row,
    text="📢 CÒI\n  OFF",
    command=toggle_horn,
    width=11,
    height=2,
    bg=PANEL2,
    fg=GRAY,
    font=FONT_MED,
    relief="flat",
    cursor="hand2",
    activebackground=BTN_HOVER
)
btn_horn.pack(side="left", padx=4)

btn_police = tk.Button(
    horn_row,
    text="🚨 CẢNH SÁT\n  OFF",
    command=toggle_police,
    width=13,
    height=2,
    bg=PANEL2,
    fg=GRAY,
    font=FONT_MED,
    relief="flat",
    cursor="hand2",
    activebackground=BTN_HOVER
)
btn_police.pack(side="left", padx=4)

tk.Label(
    p_horn,
    text="Còi cảnh sát nháy đèn LED trái/phải trên xe",
    bg=PANEL,
    fg=GRAY2,
    font=FONT_SMALL
).pack(anchor="w", pady=(0, 2))

p_outer8, p_log = make_panel(col_right, "  SYSTEM LOG")
p_outer8.pack(fill="both", expand=True, pady=6)

log_box = scrolledtext.ScrolledText(
    p_log,
    height=8,
    state='disabled',
    bg="#07070f",
    fg=WHITE,
    font=FONT_MONO,
    relief="flat",
    insertbackground=CYAN,
    selectbackground=CYAN_DIM
)
log_box.pack(fill="both", expand=True)
log_box.tag_config("danger", foreground=RED)
log_box.tag_config("info",   foreground=CYAN)
log_box.tag_config("normal", foreground=WHITE)

def clear_log():
    log_box.config(state='normal')
    log_box.delete('1.0', tk.END)
    log_box.config(state='disabled')

tk.Button(
    p_log,
    text="CLR",
    command=clear_log,
    bg=PANEL2,
    fg=GRAY,
    font=FONT_SMALL,
    relief="flat",
    cursor="hand2",
    pady=2
).pack(anchor="e", pady=2)

tk.Frame(root, bg=CYAN, height=1).pack(fill="x")

status_bar = tk.Frame(root, bg=PANEL, pady=4)
status_bar.pack(fill="x")

tk.Label(
    status_bar,
    text="  ◈ ESP32 RC Car Control Dashboard  |  v3.0  |  Python + tkinter",
    bg=PANEL,
    fg=GRAY,
    font=FONT_SMALL
).pack(side="left")

tk.Label(
    status_bar,
    text="[ H=Đèn  Z=Còi  WASD=Di chuyển  Space=Dừng ]  ",
    bg=PANEL,
    fg=GRAY2,
    font=FONT_SMALL
).pack(side="right")

root.bind("<KeyPress>",   key_press)
root.bind("<KeyRelease>", key_release)

update_clock()

log("Hệ thống khởi động. Nhập IP và nhấn CONNECT.", "info")
log("Phím tắt: WASD/Arrow=Di chuyển  H=Đèn  Z=Còi  Space=Dừng", "normal")

root.mainloop()
