#include <GxEPD2_3C.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <esp_sleep.h>

#include "secrets.h"

#define EPD_PWR 2
#define EPD_CS 5
#define EPD_DC 17
#define EPD_RST 16
#define EPD_BUSY 4

// Battery measurement: LaskaKit ESPink has a resistive divider on ADC.
// VERIFY ON YOUR BOARD: wrong pin/ratio → nonsense voltage. Comment out the
// whole block (or #undef BAT_ADC_PIN) if you have no divider; telemetry will
// then omit vbat.
#define BAT_ADC_PIN 34 // ADC1, typically GPIO34 - verify for your board revision
#define BAT_DIVIDER 2.0 // Vbat = Vadc * BAT_DIVIDER (adjust to match actual divider)

#define DEFAULT_SLEEP_SECONDS 1800UL // 30 min
#define MIN_SLEEP_SECONDS 60UL // 1 min
#define MAX_SLEEP_SECONDS 28800UL // 8 h — lets the server request a long night sleep

// Timeout for best-effort telemetry (connect + read).
#define TELEMETRY_TIMEOUT_MS 2500

// API endpoint paths, appended to SECRET_API_PREFIX (from secrets.h).
#define API_IMAGE_PATH "/api/v1/image.bin"
#define API_TELEMETRY_PATH "/api/v1/telemetry"

// GDEY116Z91: 960x640, 3-color (black/white/red), SSD1677
// Page buffer reduced to HEIGHT/4 — we stream via writeImage() and never use the
// internal paged buffer, saving ~38 kB of static RAM (otherwise DRAM overflows).
GxEPD2_3C<GxEPD2_1160c_GDEY116Z91, GxEPD2_1160c_GDEY116Z91::HEIGHT / 4> display(GxEPD2_1160c_GDEY116Z91(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY));

// Native panel dimensions (writeImage always works in native orientation, ignoring rotation).
static const int16_t W = 960;
static const int16_t H = 640;
static const int STRIDE = W / 8; // 120 bytes per row
static const int STRIP_H = 80; // strip height (640 / 80 = 8 strips)

// Buffers for one strip (static → no allocation, no fragmentation).
uint8_t blackStrip[STRIDE * STRIP_H]; // 9600 B
uint8_t redStrip[STRIDE * STRIP_H]; // 9600 B

// Result of fetching a frame: whether the full image was streamed and how long to sleep next.
struct FrameResult {
    bool imageOk = false; // full frame written to controller RAM (safe to refresh)
    bool haveSleep = false; // server provided a valid next-wakeup time
    uint32_t sleepSeconds = 0; // computed sleep duration (valid only when haveSleep)
};

/** @brief Connects to WiFi
 * @return true on success, false on timeout or credential error.
 */
bool connectWiFi(unsigned timeout_ms)
{
    Serial.printf("Connecting to WiFi \"%s\"", SECRET_WIFI_ESSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(SECRET_WIFI_ESSID, SECRET_WIFI_PASSWORD);

    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < timeout_ms) {
        delay(250);
        Serial.print(".");
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        Serial.print("Connected, IP: ");
        Serial.println(WiFi.localIP());
        return true;
    }
    Serial.println("WiFi connection failed");
    return false;
}

/** @brief Reads exactly len bytes from the stream into buf, or fails on timeout.
 */
bool readFully(WiFiClient* s, uint8_t* buf, size_t len, uint32_t timeoutMs)
{
    size_t got = 0;
    unsigned long last = millis();
    while (got < len) {
        int n = s->read(buf + got, len - got);
        if (n > 0) {
            got += n;
            last = millis();
        } else {
            if (millis() - last > timeoutMs)
                return false;
            delay(2);
        }
    }
    return true;
}

/** Converts (y, m, d) to days since 1970-01-01 (Howard Hinnant, works for dates before 1970).
 */
static int64_t daysFromCivil(int y, unsigned m, unsigned d)
{
    y -= m <= 2;
    int64_t era = (y >= 0 ? y : y - 399) / 400;
    unsigned yoe = (unsigned)(y - era * 400);
    unsigned doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
    unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097 + (int64_t)doe - 719468;
}

/** @brief Parses an HTTP Date header (RFC 1123, always GMT) into a Unix epoch. Example: "Wed, 09 Jul 2026 12:00:00 GMT"
 */
static bool parseHttpDate(const char* s, time_t& out)
{
    if (!s || !*s)
        return false;
    static const char* months = "JanFebMarAprMayJunJulAugSepOctNovDec";
    char mon[4] = {0};
    int d, y, hh, mm, ss;
    // Skip weekday name and comma: "Www, dd Mon yyyy hh:mm:ss GMT"
    if (sscanf(s, "%*3s %d %3s %d %d:%d:%d", &d, mon, &y, &hh, &mm, &ss) != 6) {
        // Some servers include the comma — try that variant too.
        if (sscanf(s, "%*3s, %d %3s %d %d:%d:%d", &d, mon, &y, &hh, &mm, &ss) != 6)
            return false;
    }
    const char* p = strstr(months, mon);
    if (!p)
        return false;
    unsigned month = (p - months) / 3 + 1;
    out = (time_t)(daysFromCivil(y, month, d) * 86400LL + hh * 3600 + mm * 60 + ss);
    return true;
}

/**
 * Downloads the image in strips into controller RAM and computes next wakeup from headers.
 * Does NOT refresh! renderFrame() does that only on success. On error the old image stays.
 */
FrameResult fetchFrame()
{
    FrameResult r;
    HTTPClient http;
    WiFiClient client;

    String url = String(SECRET_API_PREFIX) + API_IMAGE_PATH;
    Serial.printf("GET %s\n", url.c_str());
    if (!http.begin(client, url)) {
        Serial.println("http.begin failed");
        return r;
    }

    // Collect these headers before HTTPClient discards them.
    const char* wantHeaders[] = {"X-Next-Wakeup", "Date"};
    http.collectHeaders(wantHeaders, 2);

    int code = http.GET();
    if (code != HTTP_CODE_OK) {
        Serial.printf("HTTP error: %d\n", code);
        http.end();
        return r;
    }

    // Next wakeup: X-Next-Wakeup is an absolute epoch; "now" comes from Date.
    // sleep = X-Next-Wakeup - Date. No NTP needed.
    String nw = http.header("X-Next-Wakeup");
    if (nw.length()) {
        time_t next = (time_t)strtoul(nw.c_str(), nullptr, 10);
        time_t now;
        if (parseHttpDate(http.header("Date").c_str(), now) && next > now) {
            r.haveSleep = true;
            r.sleepSeconds = (uint32_t)(next - now);
            Serial.printf("Server: next=%ld now=%ld -> sleep=%us\n", (long)next, (long)now, r.sleepSeconds);
        } else {
            Serial.println("X-Next-Wakeup present but Date unreadable / in the past");
        }
    }

    WiFiClient* stream = http.getStreamPtr();
    for (int y = 0; y < H; y += STRIP_H) {
        int sh = (H - y < STRIP_H) ? (H - y) : STRIP_H;
        size_t nb = (size_t)STRIDE * sh;

        if (!readFully(stream, blackStrip, nb, 5000) || !readFully(stream, redStrip, nb, 5000)) {
            Serial.printf("Timeout/short stream at strip y=%d\n", y);
            http.end();
            return r; // imageOk stays false → no refresh
        }

        // Write strip directly into controller RAM (not visible until refresh).
        display.writeImage(blackStrip, redStrip, 0, y, W, sh);
    }
    http.end();

    r.imageOk = true;
    return r;
}

/**
 * Issues a full refresh of the frame. GxEPD2 refresh is void with an internal busy-wait  timeout, so "success" means the full frame was streamed and refresh was issued.
 * Called only when imageOk to avoid a partial image on screen.
 */
bool renderFrame(const FrameResult& r)
{
    if (!r.imageOk)
        return false;
    display.refresh(false);
    return true;
}

/** @brief Reads battery voltage from ADC (calibrated mV → V via divider). Returns NAN if unavailable. */
float readBattery()
{
#ifdef BAT_ADC_PIN
    uint32_t mv = analogReadMilliVolts(BAT_ADC_PIN);
    return mv / 1000.0f * BAT_DIVIDER;
#else
    return NAN;
#endif
}

/** @brief Returns a wakeup reason string without needing to persist anything across sleep. */
const char* wakeReason()
{
    switch (esp_sleep_get_wakeup_cause()) {
    case ESP_SLEEP_WAKEUP_TIMER:
        return "timer";
    default:
        return "poweron"; // first boot / reset / battery disconnect
    }
}

/** @brief Best-effort telemetry: POST JSON, short timeout, result ignored.
 *  @param sleepSeconds the sleep about to be taken — the interval until the next
 *         expected check-in, so the server can flag genuinely missed updates.
 *  @param retries number of extra fetch attempts beyond the first (0 = clean fetch). */
void postTelemetry(bool renderOk, uint32_t sleepSeconds, int retries)
{
    char body[224];
    int len = snprintf(body, sizeof(body), "{\"rssi\":%d,\"heap\":%u,\"render_ok\":%s,\"wake\":\"%s\",\"sleep\":%u,\"retries\":%d", WiFi.RSSI(), (unsigned)ESP.getFreeHeap(), renderOk ? "true" : "false", wakeReason(), (unsigned)sleepSeconds, retries);

    float vbat = readBattery();
    if (!isnan(vbat)) {
        len += snprintf(body + len, sizeof(body) - len, ",\"vbat\":%.2f", vbat);
    }
    len += snprintf(body + len, sizeof(body) - len, "}");

    HTTPClient http;
    WiFiClient client;
    http.setConnectTimeout(TELEMETRY_TIMEOUT_MS);
    http.setTimeout(TELEMETRY_TIMEOUT_MS);
    String url = String(SECRET_API_PREFIX) + API_TELEMETRY_PATH;
    if (!http.begin(client, url)) {
        Serial.println("Telemetry: http.begin failed (ignoring)");
        return;
    }
    http.addHeader("Content-Type", "application/json");
    int code = http.POST((uint8_t*)body, len);
    Serial.printf("Telemetry POST -> %d: %s\n", code, body);
    http.end();
}

/** @brief Disconnects WiFi, hibernates the display, cuts power, then enters deep sleep (timer wakeup). */
void goToSleep(uint32_t seconds)
{
    if (seconds < MIN_SLEEP_SECONDS)
        seconds = MIN_SLEEP_SECONDS;
    if (seconds > MAX_SLEEP_SECONDS)
        seconds = MAX_SLEEP_SECONDS;

    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);
    display.hibernate();
    digitalWrite(EPD_PWR, LOW); // e-paper holds image without power

    esp_sleep_enable_timer_wakeup((uint64_t)seconds * 1000000ULL);
    Serial.printf("Deep sleep for %u s...\n", seconds);
    Serial.flush();
    esp_deep_sleep_start(); // chip restarts on wakeup → execution resumes from setup()
}

void setup()
{
    Serial.begin(115200);

    pinMode(EPD_PWR, OUTPUT);
    digitalWrite(EPD_PWR, HIGH); // power on e-paper
    delay(50);

    display.init(115200);
    display.setRotation(0); // irrelevant for writeImage (native 960x640)

    // Without WiFi we can do nothing, sleep and retry later.
    if (!connectWiFi(15000)) {
        goToSleep(DEFAULT_SLEEP_SECONDS);
    }

    // Fetch image + next wakeup from response headers. A fetch can fail on a
    // transient network hiccup or a short stream, so retry a couple of times
    // before giving up (up to 3 attempts total).
    FrameResult frame = fetchFrame();
    int retries = 0;
    for (; !frame.imageOk && retries < 2; retries++) {
        Serial.printf("Fetch failed, retry %d/2...\n", retries + 1);
        frame = fetchFrame();
    }

    // Render guarded so its outcome never blocks the sleep path.
    bool renderOk = renderFrame(frame);
    Serial.println(renderOk ? "Rendered." : "Fetch/render failed, display unchanged.");

    uint32_t sleepSecs = frame.haveSleep ? frame.sleepSeconds : DEFAULT_SLEEP_SECONDS;
    postTelemetry(renderOk, sleepSecs, retries);
    goToSleep(sleepSecs);
}

void loop(){}
