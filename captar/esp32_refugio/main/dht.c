#include "dht.h"

#include <stdint.h>
#include "esp_timer.h"
#include "esp_rom_sys.h"
#include "freertos/FreeRTOS.h"
#include "freertos/portmacro.h"

/* Espera a que el pin tome `nivel`; devuelve us transcurridos o -1 si supera max_us. */
static int esperar_nivel(gpio_num_t pin, int nivel, int max_us)
{
    int64_t t0 = esp_timer_get_time();
    while (gpio_get_level(pin) != nivel) {
        if (esp_timer_get_time() - t0 > max_us) {
            return -1;
        }
    }
    return (int)(esp_timer_get_time() - t0);
}

esp_err_t dht_init(gpio_num_t pin)
{
    gpio_config_t cfg = {
        .pin_bit_mask = 1ULL << pin,
        .mode = GPIO_MODE_INPUT_OUTPUT_OD,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    esp_err_t err = gpio_config(&cfg);
    if (err == ESP_OK) {
        gpio_set_level(pin, 1);
    }
    return err;
}

esp_err_t dht_leer(gpio_num_t pin, dht_tipo_t tipo, float *temp_c, float *humedad)
{
    uint8_t d[5] = {0};
    static portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;
    esp_err_t res = ESP_OK;

    /* Senal de inicio: DHT11 >= 18 ms bajo, DHT22 >= 1 ms. */
    gpio_set_level(pin, 0);
    esp_rom_delay_us(tipo == DHT_TIPO_11 ? 20000 : 2000);

    portENTER_CRITICAL(&mux);
    gpio_set_level(pin, 1);
    esp_rom_delay_us(30);

    /* Respuesta: 80 us bajo + 80 us alto. */
    if (esperar_nivel(pin, 0, 100) < 0 || esperar_nivel(pin, 1, 120) < 0 ||
        esperar_nivel(pin, 0, 120) < 0) {
        res = ESP_ERR_TIMEOUT;
    }

    /* 40 bits: ~50 us bajo, luego alto 26-28 us (0) o ~70 us (1). */
    for (int i = 0; res == ESP_OK && i < 40; i++) {
        if (esperar_nivel(pin, 1, 100) < 0) {
            res = ESP_ERR_TIMEOUT;
            break;
        }
        int alto = esperar_nivel(pin, 0, 120);
        if (alto < 0) {
            res = ESP_ERR_TIMEOUT;
            break;
        }
        d[i / 8] <<= 1;
        if (alto > 45) {
            d[i / 8] |= 1;
        }
    }
    portEXIT_CRITICAL(&mux);
    gpio_set_level(pin, 1);

    if (res != ESP_OK) {
        return res;
    }
    if ((uint8_t)(d[0] + d[1] + d[2] + d[3]) != d[4]) {
        return ESP_ERR_INVALID_CRC;
    }

    if (tipo == DHT_TIPO_11) {
        *humedad = d[0] + d[1] / 10.0f;
        float t = d[2] + (d[3] & 0x7F) / 10.0f;
        *temp_c = (d[3] & 0x80) ? -t : t;
    } else {
        *humedad = ((d[0] << 8) | d[1]) / 10.0f;
        float t = (((d[2] & 0x7F) << 8) | d[3]) / 10.0f;
        *temp_c = (d[2] & 0x80) ? -t : t;
    }
    return ESP_OK;
}
