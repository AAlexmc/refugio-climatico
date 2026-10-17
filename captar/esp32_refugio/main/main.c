/*
 * Hospital en casa: sensores de la habitacion -> JSON por linea por USB.
 *
 * ESP32 -> PC (cada CONFIG_HS_PERIODO_MS):
 *   {"temp":27.4,"humedad":48.0,"luz":0.62,"presencia":true,"rele":false}
 * Un sensor deshabilitado o con lectura fallida omite su campo; el fallo se
 * avisa con una linea aparte: {"error":"dht: checksum"}
 * PC -> ESP32:  {"rele":true}   {"buzzer":500}   (ms de pitido)
 */
#include <ctype.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "sdkconfig.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "driver/gpio.h"
#include "driver/usb_serial_jtag.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#if CONFIG_HS_BUZZER_ENABLE && CONFIG_HS_BUZZER_PASIVO
#include "driver/ledc.h"
#endif
#if CONFIG_HS_DHT_ENABLE
#include "dht.h"
#endif

/* Los bool de Kconfig en "n" no se definen: los normalizamos a 0/1. */
#ifndef CONFIG_HS_RELE_ACTIVO_BAJO
#define CONFIG_HS_RELE_ACTIVO_BAJO 0
#endif
#ifndef CONFIG_HS_LDR_INVERTIR
#define CONFIG_HS_LDR_INVERTIR 0
#endif
#ifndef CONFIG_HS_DHT_22
#define CONFIG_HS_DHT_22 0
#endif

static const char *TAG = "hospital";

#define BUZZER_MAX_MS 5000
#define DHT_PERIODO_US 2100000LL /* DHT22 exige >= 2 s entre lecturas */
#define DHT_VALIDEZ_US 10000000LL

static TaskHandle_t s_tarea_sensores;
static volatile bool s_rele;

/* ---------- salida: una sola funcion, linea completa ---------- */

static void enviar_linea(const char *s)
{
    char buf[200];
    int n = snprintf(buf, sizeof(buf), "%s\n", s);
    if (n <= 0 || n >= (int)sizeof(buf)) {
        return;
    }
    /* Con timeout: si no hay host leyendo, se descarta en vez de bloquear. */
    usb_serial_jtag_write_bytes(buf, n, pdMS_TO_TICKS(50));
}

static void enviar_error(const char *msg)
{
    char buf[80];
    snprintf(buf, sizeof(buf), "{\"error\":\"%s\"}", msg);
    enviar_linea(buf);
}

/* ---------- actuadores ---------- */

#if CONFIG_HS_RELE_ENABLE
static void rele_aplicar(bool on)
{
    s_rele = on;
    gpio_set_level(CONFIG_HS_RELE_GPIO, (on != CONFIG_HS_RELE_ACTIVO_BAJO) ? 1 : 0);
}
#endif

#if CONFIG_HS_BUZZER_ENABLE
static esp_timer_handle_t s_buzzer_timer;

static void buzzer_set(bool on)
{
#if CONFIG_HS_BUZZER_PASIVO
    ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, on ? 512 : 0);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);
#else
    gpio_set_level(CONFIG_HS_BUZZER_GPIO, on ? 1 : 0);
#endif
}

static void buzzer_off_cb(void *arg)
{
    buzzer_set(false);
}

static void buzzer_pitar(int ms)
{
    if (ms < 1) {
        return;
    }
    if (ms > BUZZER_MAX_MS) {
        ms = BUZZER_MAX_MS;
    }
    esp_timer_stop(s_buzzer_timer); /* error si no estaba activo: se ignora */
    buzzer_set(true);
    esp_timer_start_once(s_buzzer_timer, (uint64_t)ms * 1000ULL);
}

static void buzzer_init(void)
{
#if CONFIG_HS_BUZZER_PASIVO
    ledc_timer_config_t t = {
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .duty_resolution = LEDC_TIMER_10_BIT,
        .timer_num = LEDC_TIMER_0,
        .freq_hz = CONFIG_HS_BUZZER_FREQ_HZ,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    ledc_channel_config_t c = {
        .gpio_num = CONFIG_HS_BUZZER_GPIO,
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel = LEDC_CHANNEL_0,
        .timer_sel = LEDC_TIMER_0,
        .duty = 0,
        .hpoint = 0,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&t));
    ESP_ERROR_CHECK(ledc_channel_config(&c));
#else
    gpio_config_t cfg = {
        .pin_bit_mask = 1ULL << CONFIG_HS_BUZZER_GPIO,
        .mode = GPIO_MODE_OUTPUT,
    };
    ESP_ERROR_CHECK(gpio_config(&cfg));
    gpio_set_level(CONFIG_HS_BUZZER_GPIO, 0);
#endif
    const esp_timer_create_args_t args = {.callback = buzzer_off_cb, .name = "buzzer_off"};
    ESP_ERROR_CHECK(esp_timer_create(&args, &s_buzzer_timer));
}
#endif

/* ---------- comandos entrantes ---------- */

/* Valor tras "clave": en la linea, o NULL. Solo claves planas del protocolo. */
static const char *valor_de(const char *linea, const char *clave)
{
    char patron[24];
    snprintf(patron, sizeof(patron), "\"%s\"", clave);
    const char *p = strstr(linea, patron);
    if (!p) {
        return NULL;
    }
    p = strchr(p + strlen(patron), ':');
    if (!p) {
        return NULL;
    }
    p++;
    while (*p && isspace((unsigned char)*p)) {
        p++;
    }
    return p;
}

static void procesar_linea(const char *linea)
{
    bool cambio = false;
#if CONFIG_HS_RELE_ENABLE
    const char *v = valor_de(linea, "rele");
    if (v) {
        if (strncmp(v, "true", 4) == 0) {
            rele_aplicar(true);
            cambio = true;
        } else if (strncmp(v, "false", 5) == 0) {
            rele_aplicar(false);
            cambio = true;
        }
    }
#endif
#if CONFIG_HS_BUZZER_ENABLE
    const char *b = valor_de(linea, "buzzer");
    if (b && (isdigit((unsigned char)*b))) {
        buzzer_pitar(atoi(b));
        cambio = true;
    }
#endif
    if (cambio && s_tarea_sensores) {
        xTaskNotifyGive(s_tarea_sensores); /* responde ya con una linea de estado */
    }
}

static void tarea_comandos(void *arg)
{
    char linea[96];
    size_t n = 0;
    bool descartar = false; /* linea demasiado larga: se tira hasta el \n */
    uint8_t c;
    for (;;) {
        int r = usb_serial_jtag_read_bytes(&c, 1, portMAX_DELAY);
        if (r != 1) {
            continue;
        }
        if (c == '\n' || c == '\r') {
            if (n > 0 && !descartar) {
                linea[n] = '\0';
                procesar_linea(linea);
            }
            n = 0;
            descartar = false;
        } else if (n < sizeof(linea) - 1) {
            linea[n++] = (char)c;
        } else {
            descartar = true;
        }
    }
}

/* ---------- sensores ---------- */

#if CONFIG_HS_LDR_ENABLE
static adc_oneshot_unit_handle_t s_adc;
static adc_channel_t s_ldr_canal;

static void ldr_init(void)
{
    adc_unit_t unidad;
    ESP_ERROR_CHECK(adc_oneshot_io_to_channel(CONFIG_HS_LDR_GPIO, &unidad, &s_ldr_canal));
    adc_oneshot_unit_init_cfg_t u = {.unit_id = unidad};
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&u, &s_adc));
    adc_oneshot_chan_cfg_t c = {.atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_DEFAULT};
    ESP_ERROR_CHECK(adc_oneshot_config_channel(s_adc, s_ldr_canal, &c));
}

static bool ldr_leer(float *luz)
{
    int suma = 0;
    for (int i = 0; i < 8; i++) {
        int raw;
        if (adc_oneshot_read(s_adc, s_ldr_canal, &raw) != ESP_OK) {
            return false;
        }
        suma += raw;
    }
    float v = (suma / 8.0f) / 4095.0f;
    if (v > 1.0f) {
        v = 1.0f;
    }
    *luz = CONFIG_HS_LDR_INVERTIR ? 1.0f - v : v;
    return true;
}
#endif

static void tarea_sensores(void *arg)
{
#if CONFIG_HS_DHT_ENABLE
    float temp = 0, hum = 0;
    bool dht_ok = false;
    int64_t dht_t_ok = 0;
    int64_t dht_t_intento = -DHT_PERIODO_US;
#endif
    for (;;) {
        char buf[160];
        size_t n = 0;
        n += snprintf(buf + n, sizeof(buf) - n, "{");
        const char *sep = "";
        (void)sep;

#if CONFIG_HS_DHT_ENABLE
        int64_t ahora = esp_timer_get_time();
        if (ahora - dht_t_intento >= DHT_PERIODO_US) {
            dht_t_intento = ahora;
            esp_err_t e = dht_leer(CONFIG_HS_DHT_GPIO,
                                   CONFIG_HS_DHT_22 ? DHT_TIPO_22 : DHT_TIPO_11, &temp, &hum);
            dht_ok = (e == ESP_OK);
            if (dht_ok) {
                dht_t_ok = ahora;
            } else {
                enviar_error(e == ESP_ERR_INVALID_CRC ? "dht: checksum" : "dht: timeout");
            }
        }
        /* Entre lecturas se repite la ultima buena; si falla, el campo se omite. */
        if (dht_ok && ahora - dht_t_ok < DHT_VALIDEZ_US) {
            n += snprintf(buf + n, sizeof(buf) - n, "%s\"temp\":%.1f,\"humedad\":%.1f",
                          sep, temp, hum);
            sep = ",";
        }
#endif
#if CONFIG_HS_LDR_ENABLE
        float luz;
        if (ldr_leer(&luz)) {
            n += snprintf(buf + n, sizeof(buf) - n, "%s\"luz\":%.2f", sep, luz);
            sep = ",";
        } else {
            enviar_error("ldr: adc");
        }
#endif
#if CONFIG_HS_PIR_ENABLE
        n += snprintf(buf + n, sizeof(buf) - n, "%s\"presencia\":%s", sep,
                      gpio_get_level(CONFIG_HS_PIR_GPIO) ? "true" : "false");
        sep = ",";
#endif
#if CONFIG_HS_RELE_ENABLE
        n += snprintf(buf + n, sizeof(buf) - n, "%s\"rele\":%s", sep, s_rele ? "true" : "false");
        sep = ",";
#endif
        snprintf(buf + n, sizeof(buf) - n, "}");
        enviar_linea(buf);

        /* Duerme el periodo o hasta que llegue un comando (respuesta inmediata). */
        ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(CONFIG_HS_PERIODO_MS));
    }
}

void app_main(void)
{
    usb_serial_jtag_driver_config_t usb = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&usb));

#if CONFIG_HS_DHT_ENABLE
    ESP_ERROR_CHECK(dht_init(CONFIG_HS_DHT_GPIO));
#endif
#if CONFIG_HS_LDR_ENABLE
    ldr_init();
#endif
#if CONFIG_HS_PIR_ENABLE
    gpio_config_t pir = {
        .pin_bit_mask = 1ULL << CONFIG_HS_PIR_GPIO,
        .mode = GPIO_MODE_INPUT,
    };
    ESP_ERROR_CHECK(gpio_config(&pir));
#endif
#if CONFIG_HS_RELE_ENABLE
    gpio_config_t rele = {
        .pin_bit_mask = 1ULL << CONFIG_HS_RELE_GPIO,
        .mode = GPIO_MODE_OUTPUT,
    };
    ESP_ERROR_CHECK(gpio_config(&rele));
    rele_aplicar(false);
#endif
#if CONFIG_HS_BUZZER_ENABLE
    buzzer_init();
#endif

    xTaskCreate(tarea_sensores, "sensores", 4096, NULL, 5, &s_tarea_sensores);
    xTaskCreate(tarea_comandos, "comandos", 4096, NULL, 4, NULL);
    ESP_LOGI(TAG, "listo");
}
