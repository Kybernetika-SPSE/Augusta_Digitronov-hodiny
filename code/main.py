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

# --- NASTAVENÍ PINŮ PODLE SCHÉMATU ---
btn_start_stop = Pin(23, Pin.IN) 
btn_plus_one   = Pin(32, Pin.IN) 
btn_switch     = Pin(33, Pin.IN) 

# Posuvné registry 74HC595
pin_ser   = Pin(27, Pin.OUT) 
pin_srclk = Pin(26, Pin.OUT) 
pin_rlck  = Pin(25, Pin.OUT) 
pin_oe    = Pin(22, Pin.OUT)  

# NOVÉ PINY: Měnič a Tečky
pin_shdn  = Pin(13, Pin.OUT) # SHDN - Zapínání 170V měniče (IO14)
pin_dots  = Pin(2, Pin.OUT)  # D2 - Zapínání teček mezi číslicemi (GPIO 2)

# --- INICIALIZACE I2C a SENZORŮ ---
i2c = I2C(0, scl=Pin(4), sda=Pin(18), freq=400000)

if i2c_available:
    rtc = ds3231.DS3231(i2c)
    sensor = vl53l0x.VL53L0X(i2c) # Tady ho rovnou pojmenujeme sensor

# --- GLORBO FLORBO
current_hour = 12
current_minute = 34
display_on = False
frozen_time = False
freeze_start_time = 0
set_mode = 0 # 0 = Běžný provoz, 1 = Nastavení HODIN, 2 = Nastavení MINUT


posledni_pohyb_cas = time.ticks_ms() 

# --- Fce ---
def turn_on_display():
    global display_on
    pin_oe.value(0)   
    pin_shdn.value(0) 
    display_on = True

def turn_off_display():
    global display_on
    pin_shdn.value(1) 
    pin_oe.value(1)  
    pin_dots.value(0) 
    display_on = False

def dec_to_bcd(val):
    """Převede klasické číslo (např. 34) na BCD formát pro K155ID1"""
    tens = val // 10
    units = val % 10
    return (tens << 4) | units

def update_shift_registers(hours, minutes):
    """Pošle 16 bitů do kaskády dvou 74HC595"""
    bcd_hours = dec_to_bcd(hours)
    bcd_minutes = dec_to_bcd(minutes)
    
    # min:hod
    data_to_send = (bcd_hours << 8) | bcd_minutes
    
    # Nastavění hodnot
    for i in range(15, -1, -1):
        bit = (data_to_send >> i) & 1
        pin_ser.value(bit)
          
        pin_srclk.value(1)
        pin_srclk.value(0)
        
    pin_rlck.value(1)
    pin_rlck.value(0)



# --- HLAVNÍ SMYČÁK  ---
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
            
    # === ČTENÍ REÁLNÉHO ČASU Z RTC ===
    if i2c_available and set_mode == 0 and not frozen_time:
        try:
            cas = rtc.datetime() 
        
            current_hour = cas[4]   # Přepíše tu 12
            current_minute = cas[5] # Přepíše tu 34
        except:
            pass
            
    # 2. ZHASÍNÁNÍ DIGITRONEK
    if display_on and set_mode == 0:
        if time.ticks_diff(now, posledni_pohyb_cas) > 5000:
            turn_off_display()

    # 3. DOTS
    if display_on:
        if set_mode == 0:
            if (now % 1000) < 500:
                pin_dots.value(1)
            else:
                pin_dots.value(0)
        else:
            pin_dots.value(1) 
    
    # 4. Zmrazení času 
    if btn_start_stop.value() == 0:
        if not frozen_time:
            frozen_time = True
            freeze_start_time = now
        time.sleep(0.3)
            
    if frozen_time and time.ticks_diff(now, freeze_start_time) > 10000:
        frozen_time = False

   # 5. Přepínání režimů nastavení (Switch) a ULOŽENÍ ČASU
    if btn_switch.value() == 0:
        stary_rezim = set_mode
        set_mode = (set_mode + 1) % 3
        

        if stary_rezim != 0 and set_mode == 0 and i2c_available:
            try:
                novy_cas = (2025, 30,1, current_hour, current_minute, 0, 0)
                
                rtc.datetime(novy_cas)
            except:
                pass

        posledni_pohyb_cas = now
        if not display_on: turn_on_display()
        time.sleep(0.3)

    # 6. Přidávání času (+1)
    if btn_plus_one.value() == 0:
        if set_mode == 1:
            current_hour = (current_hour + 1) % 24
        elif set_mode == 2:
            current_minute = (current_minute + 1) % 60
        posledni_pohyb_cas = now 
        if not display_on: turn_on_display()
        time.sleep(0.2) 

    # 7. Zobrazení 
    if display_on:
        update_shift_registers(current_hour, current_minute)
    
    time.sleep(0.05)