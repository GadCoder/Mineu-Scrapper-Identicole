import os
import time
import json

import mysql.connector
import requests
from dotenv import load_dotenv

from insert_school_data import insert_school
from models.location_data import LocationData

load_dotenv()


def create_sql_connection(database: str):
    connection = mysql.connector.connect(
        host=os.getenv("host"),
        user=os.getenv("user"),
        password=os.getenv("password"),
        database=database,
    )
    return connection


def get_departments_data(connection, database: str):
    cursor = connection.cursor()
    query = f"""
        SELECT
            region.name, region.code,
            p.name, p.province_code,
            d.name, d.district_code
        FROM region
        INNER JOIN {database}.province p on region.code = p.region_code
        INNER JOIN {database}.district d on p.code = d.province_code;
    """
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    return results


def transform_location_data(locations: list) -> list[LocationData]:
    location_data = []
    for location in locations:
        location_data.append(LocationData(location=location))
    return location_data


def get_schools_from_location(
    location: LocationData, connection, modality: str, stage: str
):
    data = get_request_data(location=location, modality=modality, stage=stage)
    page_number = 0
    schools_founded = 0
    location_name = f"{location.region_name}-{location.province_name}"
    while True:
        schools_from_page = get_schools_from_page(
            location_name=location_name,
            page=page_number,
            data=data,
            connection=connection,
        )
        if schools_from_page == 0:
            return schools_founded
        schools_founded += schools_from_page
        page_number += 12


def get_request_data(location: LocationData, modality: str, stage: str):
    data = {
        "accion": "Detalle",
        "ubicacion": "1",
        "s_departament_geo": location.region_code,
        "s_province_geo": location.province_code,
        "s_district_geo	": location.district_code,
        "txt_cen_edu": "",
        "modalidad": modality,
        "s_nivel": stage,
        "vacante": "3",
        "participa": "3",
        "dot-amount": "5",
        "genero": "",
    }
    return data


def get_schools_from_page(location_name: str, page: int, data: dict, connection):
    base_url = "https://identicole.minedu.gob.pe/colegio/busqueda_colegios_detalle"
    url = base_url if page == 0 else f"{base_url}/{page}"
    response = requests.post(url, data=data)
    status_code = response.status_code
    if status_code != 200:
        print(f"! Error al obtener colegios para {location_name} -> {status_code}")
        return 0
    parts = response.text.split("||")
    if len(parts) < 4:
        print(f"! No se encontraron colegios para {location_name} - page {page}")
        return 0
    schools = json.loads(parts[3])
    if not schools:
        return 0
    save_schools_from_page(connection=connection, schools=schools)
    return len(schools)


def save_schools_from_page(connection, schools):
    for school in schools:
        try:
            insert_school(connection=connection, json_data=school)
        except Exception as e:
            continue


def main():
    database = "schools_data_base"
    connection = create_sql_connection(database=database)
    locations = get_departments_data(connection=connection, database=database)
    location_data: list[LocationData] = transform_location_data(locations=locations)
    modalities = ["01", "03", "04"]
    stages = ["A1,A2,A3", "B0", "A5", "F0"]
    start_time = time.time()
    for location in location_data:
        schools_founded = 0
        location_name = f"{location.region_name}-{location.province_name}"
        print(f"Getting schools for {location_name}")
        for modality in modalities:
            for stage in stages:
                schools_founded += get_schools_from_location(
                    location=location,
                    connection=connection,
                    modality=modality,
                    stage=stage,
                )
        print(f"\tFounded {schools_founded} schools for {location_name}")

    end_time = time.time()
    elapsed_time_seconds = end_time - start_time
    elapsed_time_minutes = elapsed_time_seconds / 60

    print(f"Elapsed time: {elapsed_time_minutes:.2f} minutes")


if __name__ == "__main__":
    main()
