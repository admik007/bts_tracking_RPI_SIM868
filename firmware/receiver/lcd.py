"""1.44 inch ST7735 LCD, ported from the project's original Pico receiver.

SPI1 LCD pins: DC=GP8, CS=GP9, SCK=GP10, MOSI=GP11,
RESET=GP12, BACKLIGHT=GP13. SPI0/GP16-19 remain for the SD.
Only display output; buttons are not configured here.
"""
import time
import framebuf
from machine import Pin, SPI, PWM

DC = 8
CS = 9
SCK = 10
MOSI = 11
RST = 12
BL = 13

class LCD_1inch44(framebuf.FrameBuffer):
    def __init__(self):
        self.width = 128
        self.height = 128

        self.cs = Pin(CS,Pin.OUT)
        self.rst = Pin(RST,Pin.OUT)

        self.cs(1)
        self.spi = SPI(1)
        self.spi = SPI(1,1000_000)
        self.spi = SPI(1,10000_000,polarity=0, phase=0,sck=Pin(SCK),mosi=Pin(MOSI),miso=None)
        self.dc = Pin(DC,Pin.OUT)
        self.dc(1)
        self.buffer = bytearray(self.height * self.width * 2)
        super().__init__(self.buffer, self.width, self.height, framebuf.RGB565)
        self.init_display()


        self.WHITE   = 0xFFFF
        self.BLACK   = 0x0000
        self.GREEN   = 0x001F
        self.RED     = 0xF800
        self.BLUE    = 0x07E0
        self.GBLUE   = 0X07FF
        self.YELLOW  = 0xFFE0

        self.ORANGE  = 0xFFA500
        self.MAGENTA = 0xFF00FF
        self.LGREEN  = 0x90EE90
        self.LBLUE   = 0xADD8E6


    def write_cmd(self, cmd):
        self.cs(1)
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([cmd]))
        self.cs(1)

    def write_data(self, buf):
        self.cs(1)
        self.dc(1)
        self.cs(0)
        self.spi.write(bytearray([buf]))
        self.cs(1)

    def init_display(self):
        """Initialize dispaly"""
        self.rst(1)
        self.rst(0)
        time.sleep_ms(20)
        self.rst(1)
        time.sleep_ms(120)

        self.write_cmd(0x36);
        self.write_data(0x70);

        self.write_cmd(0x3A);
        self.write_data(0x05);

         #ST7735R Frame Rate
        self.write_cmd(0xB1);
        self.write_data(0x01);
        self.write_data(0x2C);
        self.write_data(0x2D);

        self.write_cmd(0xB2);
        self.write_data(0x01);
        self.write_data(0x2C);
        self.write_data(0x2D);

        self.write_cmd(0xB3);
        self.write_data(0x01);
        self.write_data(0x2C);
        self.write_data(0x2D);
        self.write_data(0x01);
        self.write_data(0x2C);
        self.write_data(0x2D);

        self.write_cmd(0xB4); #Column inversion
        self.write_data(0x07);

        #ST7735R Power Sequence
        self.write_cmd(0xC0);
        self.write_data(0xA2);
        self.write_data(0x02);
        self.write_data(0x84);
        self.write_cmd(0xC1);
        self.write_data(0xC5);

        self.write_cmd(0xC2);
        self.write_data(0x0A);
        self.write_data(0x00);

        self.write_cmd(0xC3);
        self.write_data(0x8A);
        self.write_data(0x2A);
        self.write_cmd(0xC4);
        self.write_data(0x8A);
        self.write_data(0xEE);

        self.write_cmd(0xC5); #VCOM
        self.write_data(0x0E);

        #ST7735R Gamma Sequence
        self.write_cmd(0xe0);
        self.write_data(0x0f);
        self.write_data(0x1a);
        self.write_data(0x0f);
        self.write_data(0x18);
        self.write_data(0x2f);
        self.write_data(0x28);
        self.write_data(0x20);
        self.write_data(0x22);
        self.write_data(0x1f);
        self.write_data(0x1b);
        self.write_data(0x23);
        self.write_data(0x37);
        self.write_data(0x00);
        self.write_data(0x07);
        self.write_data(0x02);
        self.write_data(0x10);

        self.write_cmd(0xe1);
        self.write_data(0x0f);
        self.write_data(0x1b);
        self.write_data(0x0f);
        self.write_data(0x17);
        self.write_data(0x33);
        self.write_data(0x2c);
        self.write_data(0x29);
        self.write_data(0x2e);
        self.write_data(0x30);
        self.write_data(0x30);
        self.write_data(0x39);
        self.write_data(0x3f);
        self.write_data(0x00);
        self.write_data(0x07);
        self.write_data(0x03);
        self.write_data(0x10);

        self.write_cmd(0xF0); #Enable test command
        self.write_data(0x01);

        self.write_cmd(0xF6); #Disable ram power save mode
        self.write_data(0x00);
            #sleep out
        self.write_cmd(0x11);
        time.sleep_ms(120)
        #Turn on the LCD display
        self.write_cmd(0x29);

    def show(self):
        self.write_cmd(0x2A)
        self.write_data(0x00)
        self.write_data(0x01)
        self.write_data(0x00)
        self.write_data(0x80)

        self.write_cmd(0x2B)
        self.write_data(0x00)
        self.write_data(0x02)
        self.write_data(0x00)
        self.write_data(0x82)

        self.write_cmd(0x2C)

        self.cs(1)
        self.dc(1)
        self.cs(0)
        self.spi.write(self.buffer)
        self.cs(1)

class StatusLCD:
    def __init__(self):
        self.backlight = PWM(Pin(BL))
        self.backlight.freq(1000)
        self.backlight.duty_u16(32768)
        self.lcd = LCD_1inch44()
        self.render(False, 0, {}, "WAITING")

    def render(self, sd_ok, saved, senders, state="RECEIVING"):
        lcd = self.lcd
        lcd.fill(lcd.BLACK)
        lcd.text("BTS TRACKING", 4, 2, lcd.WHITE)
        lcd.hline(0, 13, 128, lcd.WHITE)
        uploading = (state.startswith("SENT:") or
                     state in ("WIFI CONNECT", "MQTT UPLOAD",
                               "UPLOAD DONE", "UPLOAD ERROR"))
        safe = state == "SAFE TO OFF"
        lcd.text("WiFi: UPLOAD" if uploading else
                 ("WiFi: OFF" if safe else "AP: 192.168.4.1"),
                 2, 17, lcd.GBLUE)
        sd_label = "OFF" if safe else ("OK" if sd_ok else "ERROR")
        lcd.text("SD: " + sd_label, 2, 30,
                 lcd.GREEN if (sd_ok or safe) else lcd.RED)
        lcd.text("Saved: {}".format(saved), 2, 43, lcd.WHITE)
        lcd.hline(0, 56, 128, lcd.WHITE)
        # Three fixed slots. Every sender is identified by its unique device ID
        # and retains its row even as measurements arrive from other senders.
        # One text line is <= 16 chars at 8 px per char.
        for idx, cells in enumerate(senders.values()):
            if idx >= 3:
                break
            operator, cid = cells[:2]
            # New receiver state carries a monotonic arrival timestamp.
            # Older two-field tuples can still render while upgrading.
            last_seen = cells[2] if len(cells) > 2 else None
            active = (last_seen is not None and
                      0 <= time.ticks_diff(time.ticks_ms(), last_seen) < 30000)
            # Two 8-pixel-high rows per sender: current cell + previous cell.
            y = 59 + idx * 17
            row = "{} {} {}".format(idx + 1, operator, cid)
            # Keep x=108 reserved for G; x=121 for the activity ring/X.
            lcd.text(row[:13], 2, y, lcd.YELLOW)
            gps_fix = cells[4] if len(cells) > 4 else False
            lcd.text("G", 108, y, lcd.GREEN if gps_fix else lcd.RED)
            previous = cells[3] if len(cells) > 3 else "-"
            lcd.text(("  prev: " + str(previous))[:16], 2, y + 8, lcd.WHITE)
            # Reserve rightmost 9 px for a 7x7 green ring or red X.
            cx, cy = 121, y + 3
            color = lcd.GREEN if active else lcd.RED
            if active:
                for dx, dy in ((-1, -3), (0, -3), (1, -3),
                               (-2, -2), (2, -2),
                               (-3, -1), (3, -1),
                               (-3, 0), (3, 0),
                               (-3, 1), (3, 1),
                               (-2, 2), (2, 2),
                               (-1, 3), (0, 3), (1, 3)):
                    lcd.pixel(cx + dx, cy + dy, color)
            else:
                for offset in range(-3, 4):
                    lcd.pixel(cx + offset, cy + offset, color)
                    lcd.pixel(cx + offset, cy - offset, color)
        lcd.text(state[:16], 2, 112,
                 lcd.GREEN if sd_ok else lcd.RED)
        lcd.show()
