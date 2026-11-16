#!/usr/bin/env python3
"""Recoge los datos del parte del mar de Sant Elm y los imprime como JSON.

Uso: python3 datos.py [dias]   (dias de previsión, 2 por defecto; 3 para el parte de la tarde)

Fuentes: Open-Meteo (oleaje MFWAM, ECMWF WAM, DWD GWAM, viento, temperatura del aire y del agua, cielo), boya de Dragonera
(Puertos del Estado, estación 2820) y boletín costero de AEMET para Illes Balears (FQXX44).
"""
import json
import re
import sys
import urllib.request

DIAS = int(sys.argv[1]) if len(sys.argv) > 1 else 2
HORAS = ("08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18")


def get(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()


def seguro(fn):
    try:
        return fn()
    except Exception as e:  # una fuente caída no debe tumbar el parte
        return {"error": str(e)}


def oleaje(modelo):
    d = json.loads(get(
        "https://marine-api.open-meteo.com/v1/marine?latitude=39.56&longitude=2.30"
        "&current=wave_height,wave_direction,wave_period,swell_wave_height,swell_wave_direction,"
        "swell_wave_period,wind_wave_height,wind_wave_direction"
        "&hourly=wave_height,wave_direction,wave_period,swell_wave_height,swell_wave_direction,"
        "wind_wave_height,wind_wave_direction"
        f"&forecast_days={DIAS}&timezone=Europe%2FMadrid&models={modelo}"))
    h = d["hourly"]
    horas = [
        {k: h[k][i] for k in h}
        for i, t in enumerate(h["time"]) if t[11:13] in HORAS
    ]
    return {"ahora": d.get("current"), "horas": horas}


def viento():
    d = json.loads(get(
        "https://api.open-meteo.com/v1/forecast?latitude=39.579&longitude=2.349"
        "&current=wind_speed_10m,wind_direction_10m,wind_gusts_10m,temperature_2m,weather_code,cloud_cover"
        "&hourly=wind_speed_10m,wind_direction_10m,wind_gusts_10m,cape,weather_code,precipitation_probability,temperature_2m,cloud_cover"
        f"&wind_speed_unit=kn&forecast_days={DIAS}&timezone=Europe%2FMadrid"))
    h = d["hourly"]
    horas = [
        {k: h[k][i] for k in h}
        for i, t in enumerate(h["time"]) if t[11:13] in HORAS
    ]
    return {"ahora": d.get("current"), "horas": horas}


def agua():
    d = json.loads(get(
        "https://marine-api.open-meteo.com/v1/marine?latitude=39.56&longitude=2.30"
        "&current=sea_surface_temperature&daily=sea_surface_temperature_max"
        f"&forecast_days={DIAS}&timezone=Europe%2FMadrid"))
    return {"ahora_c": (d.get("current") or {}).get("sea_surface_temperature"),
            "por_dia": dict(zip(d["daily"]["time"], d["daily"]["sea_surface_temperature_max"]))}


def boya():
    d = json.loads(get(
        "https://portus.puertos.es/portussvr/api/lastData/station/2820?locale=es",
        b'["WAVE"]', {"Content-Type": "application/json"}))
    v = {x["paramEseoo"]: float(x["valor"]) / x["factor"] for x in d["datos"]
         if x.get("valor") not in (None, "")}
    return {
        "fecha_utc": d.get("fecha"),
        "Hm0_m": v.get("Hm0"), "Hmax_m": v.get("Hmax"), "Tp_s": v.get("Tp"),
        "dir_media_grados": v.get("MeanDir"),
    }


def aemet():
    x = get("https://www.aemet.es/xml/maritima/FQXX44MM.xml").decode("iso-8859-15")
    limpio = lambda s: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()
    avisos = [limpio(t) for t in re.findall(r"<aviso[^>]*>.*?<texto>(.*?)</texto>", x, re.S)]
    tendencia = [limpio(t) for t in re.findall(r"<tendencia[^>]*>(.*?)</tendencia>", x, re.S)]
    zonas = {}
    for nombre, cuerpo in re.findall(r'<zona[^>]*nombre="([^"]*)"[^>]*>(.*?)</zona>', x, re.S):
        if "Mallorca" in nombre:
            zonas[nombre] = limpio(cuerpo)
    return {"avisos": avisos, "zonas_mallorca": zonas, "tendencia": tendencia}


if __name__ == "__main__":
    salida = {
        "oleaje": {m: seguro(lambda m=m: oleaje(m)) for m in ("meteofrance_wave", "ecmwf_wam025", "gwam")},
        "viento": seguro(viento),  # incluye temperatura del aire, nubes y código de tiempo
        "temperatura_agua": seguro(agua),
        "boya_dragonera": seguro(boya),
        "aemet_costero_baleares": seguro(aemet),
    }
    print(json.dumps(salida, ensure_ascii=False, indent=1))
