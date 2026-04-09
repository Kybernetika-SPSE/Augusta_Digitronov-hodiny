from machine import Pin, I2C
import time


led = Pin(2, Pin.OUT)


for i in range(1):
    led.value(1)       
    time.sleep(0.2)    
    led.value(0)       
    time.sleep(0.2)    

try:
    import ds3231
    import vl53l0x
    i2c_available = True
except ImportError:
    i2c_available = False

# --- NASTAVENI PINU PODLE SCHEMATU ---
btn_start_stop = Pin(23, Pin.IN) 
btn_plus_one   = Pin(32, Pin.IN) 
btn_switch     = Pin(33, Pin.IN) 

# Posuvne registry 74HC595
pin_ser   = Pin(27, Pin.OUT) 
pin_srclk = Pin(26, Pin.OUT) 
pin_rlck  = Pin(25, Pin.OUT) 
pin_oe    = Pin(22, Pin.OUT)  

# Bezpecne vychozi stavy pro 74HC595 (zadne nahodne pulzy pri startu)
pin_ser.value(0)
pin_srclk.value(0)
pin_rlck.value(0)
pin_oe.value(0)

# NOVE PINY: Menic a Tecky
pin_shdn  = Pin(13, Pin.OUT) # SHDN - Zapinani 170V menice (IO14)
pin_dots  = Pin(2, Pin.OUT)  # D2 - Zapinani tecek mezi cislicemi (GPIO 2)

# --- INICIALIZACE I2C a SENZORU ---
i2c = I2C(0, scl=Pin(4), sda=Pin(18), freq=400000)

if i2c_available:
    rtc = ds3231.DS3231(i2c)
    sensor = vl53l0x.VL53L0X(i2c) # Tady ho rovnou pojmenujeme sensor

# --- GLORBO FLORBO
current_hour = 00
current_minute = 00
display_on = False
frozen_time = False
freeze_start_time = 0
set_mode = 0 # 0 = Bezny provoz, 1 = Nastaveni HODIN, 2 = Nastaveni MINUT
posledni_pohyb_cas = time.ticks_ms() 

# --- Fce ---
def turn_on_display():
    global display_on
    pin_oe.value(0)   
    pin_shdn.value(1) 
    display_on = True

def turn_off_display():
    global display_on
    pin_shdn.value(0) 
    pin_oe.value(1)  
    pin_dots.value(0) 
    display_on = False

def dec_to_bcd(val):
    """Prevede klasicke cislo (napr. 34) na BCD format pro K155ID1"""
    tens = val // 10
    units = val % 10
    return (tens << 4) | units

def update_shift_registers(hours, minutes):
    bcd_hours = dec_to_bcd(hours)
    bcd_minutes = dec_to_bcd(minutes)
    
    # hod:min
    data_to_send = (bcd_hours << 8) | bcd_minutes

    # Pri shiftovani docasne vypneme vystup, aby nevznikaly artefakty.
    output_was_enabled = (pin_oe.value() == 0)
    if output_was_enabled:
        pin_oe.value(1)
    
    pin_rlck.value(0)
    for i in range(15, -1, -1):
        bit = (data_to_send >> i) & 1
        pin_ser.value(bit)

        pin_srclk.value(1)
        pin_srclk.value(0)
        
    pin_rlck.value(1)
    pin_rlck.value(0)

    if output_was_enabled:
        pin_oe.value(0)
    
    

    # --- HLAVNI SMYCAK  ---
while True:
    now = time.ticks_ms()
    
    if i2c_available:
        try:
            distance = sensor.read() 
            if distance >= 150 and distance <= 300:
                posledni_pohyb_cas = now 
                if not display_on:
                    turn_on_display()
        except:
            pass 
            
    # === CTENI REALNEHO CASU Z RTC ===
    if i2c_available and set_mode == 0 and not frozen_time:
        try:
            cas = rtc.datetime() 
        
            current_hour = cas[4]   
            current_minute = cas[5] 
        except:
            pass
            
    # 2. ZHASINANI DIGITRONEK
    if display_on and set_mode == 0:
        if time.ticks_diff(now, posledni_pohyb_cas) > 8000:
            turn_off_display()

    # 3. DOTS
    if display_on:
        if set_mode == 0:
            if (now % 2000) < 1000:
                pin_dots.value(1)
            else:
                pin_dots.value(0)
        else:
            pin_dots.value(1)
    
    # 4. Zmrazeni casu 
    if btn_start_stop.value() == 0:
        if not frozen_time:
            frozen_time = True
            freeze_start_time = now
        time.sleep(0.3)
            
    if frozen_time and time.ticks_diff(now, freeze_start_time) > 10000:
        frozen_time = False

    # 5. Prepinani rezimu nastaveni (Switch) a ULOZENI CASU
    if btn_switch.value() == 0:
        stary_rezim = set_mode
        set_mode = (set_mode + 1) % 3
        

        if stary_rezim != 0 and set_mode == 0 and i2c_available:
            try:
                novy_cas = (2025, 1, 1, current_hour, current_minute, 0, 0)
                rtc.datetime(novy_cas)
                
            except:
                pass

        posledni_pohyb_cas = now
        if not display_on: turn_on_display()
        time.sleep(0.3)

    # 6. Pridavani casu (+1)
    if btn_plus_one.value() == 0:
        if set_mode == 1:
            current_hour = (current_hour + 1) % 24
        elif set_mode == 2:
            current_minute = (current_minute + 1) % 60
        posledni_pohyb_cas = now 
        if not display_on: turn_on_display()
        time.sleep(0.2) 

    # 7. Zobrazeni 
    if display_on:
        # Pri aktivnim zobrazeni drz drivery trvale zapnute.
        pin_shdn.value(1)
        pin_oe.value(0)
        update_shift_registers(current_hour, current_minute)
    
    time.sleep(0.05)
