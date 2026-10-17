#pragma once

#include <stdbool.h>
#include "esp_err.h"
#include "driver/gpio.h"

typedef enum {
    DHT_TIPO_11,
    DHT_TIPO_22,
} dht_tipo_t;

/** Prepara el pin (open-drain + pull-up interno). */
esp_err_t dht_init(gpio_num_t pin);

/**
 * Lectura bloqueante (~25 ms, con interrupciones deshabilitadas ~5 ms).
 * Devuelve ESP_OK, ESP_ERR_TIMEOUT (sin respuesta / bit perdido) o
 * ESP_ERR_INVALID_CRC. Minimo 1 s (DHT11) / 2 s (DHT22) entre lecturas.
 */
esp_err_t dht_leer(gpio_num_t pin, dht_tipo_t tipo, float *temp_c, float *humedad);
