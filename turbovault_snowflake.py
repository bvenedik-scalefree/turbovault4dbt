import os
from configparser import ConfigParser
from procs.sqlite3 import stage
from procs.sqlite3 import satellite
from procs.sqlite3 import hub
from procs.sqlite3 import link
from procs.sqlite3 import pit
from procs.sqlite3 import nh_satellite
from logging import Logger
import pandas as pd
import sqlite3
from gooey import Gooey
from gooey import GooeyParser
from datetime import datetime

import snowflake.connector
import time

image_path = os.path.join(os.path.dirname(__file__),"images")

def connect_snowflake():
    config = ConfigParser()
    config.read(os.path.join(os.path.dirname(__file__),"config.ini"))

    database = config.get('Snowflake', 'database')
    warehouse = config.get('Snowflake', 'warehouse')
    role = config.get('Snowflake', 'role')
    schema = config.get('Snowflake', 'meta_schema')

    snowflake_credentials = ConfigParser()
    snowflake_credentials.read(config.get('Snowflake', 'credential_path'))

    user = snowflake_credentials.get('main', 'SNOWFLAKE_USER_NAME')
    password = snowflake_credentials.get('main', 'SNOWFLAKE_PASSWORD')
    
    ctx = snowflake.connector.connect(
    user= user,
    password=password,
    account=config.get('Snowflake', 'account_identifier'),
    database=database,
    warehouse=warehouse,
    role=role,
    schema=schema
    )
    
    cursor = ctx.cursor()

    sql_source_data = "SELECT * FROM source_data"
    cursor.execute(sql_source_data)
    df_source_data = cursor.fetch_pandas_all()    
    cursor.close()

    cursor = ctx.cursor()
    sql_hub_entities = "SELECT * FROM standard_hub"
    cursor.execute(sql_hub_entities)
    df_hub_entities = cursor.fetch_pandas_all()    
    cursor.close()

    cursor = ctx.cursor()
    sql_standard_satellite = "SELECT * FROM standard_satellite"
    cursor.execute(sql_standard_satellite)
    df_standard_satellite = cursor.fetch_pandas_all()    
    cursor.close()

    cursor = ctx.cursor()
    sql_link_entities = "SELECT * FROM standard_link"
    cursor.execute(sql_link_entities)
    df_link_entities = cursor.fetch_pandas_all()    
    cursor.close()
    
    cursor = ctx.cursor()
    sql_pit_entities = "SELECT * FROM pit"
    cursor.execute(sql_pit_entities)
    df_pit_entities = cursor.fetch_pandas_all()    
    cursor.close()
    
    cursor = ctx.cursor()
    sql_non_historized_satellite = "SELECT * FROM non_historized_satellite"
    cursor.execute(sql_non_historized_satellite)
    df_non_historized_satellite_entities = cursor.fetch_pandas_all()    
    cursor.close()
     
    cursor.close()
    ctx.close()
    
    dfs = { "source_data": df_source_data, 
            "hub_entities": df_hub_entities,
            "link_entities": df_link_entities, 
            "hub_satellites": df_standard_satellite,
            "pit": df_pit_entities,
            "nh_satellite": df_non_historized_satellite_entities}


    db = sqlite3.connect(':memory:')
    
    for table, df in dfs.items():
        df.to_sql(table, db)

    sqlite_cursor = db.cursor()

    return sqlite_cursor

@Gooey(
    navigation='TABBED',
    program_name='TurboVault',
    default_size=(800,800),
    advanced=True,
    image_dir=image_path)
def main():
    
    config = ConfigParser()
    config.read(os.path.join(os.path.dirname(__file__),"config.ini"))

    model_path = config.get('Snowflake','model_path')
    hashdiff_naming = config.get('Snowflake','hashdiff_naming')
    cursor = connect_snowflake()
    cursor.execute("SELECT DISTINCT SOURCE_SYSTEM || '_' || SOURCE_OBJECT FROM source_data")
    results = cursor.fetchall()
    available_sources = []

    
    for row in results:
        available_sources.append(row[0])

    generated_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    parser = GooeyParser(description='Config')
    parser.add_argument("--Tasks",help="Select the entities which You want to generate",action="append",widget='Listbox',choices=['Stage','Hub','Satellite','Link','Pit','Non Historized Satellite'],default=['Stage','Hub','Satellite','Link','Pit','Non Historized Satellite'],nargs='*',gooey_options={'height': 300})
    parser.add_argument("--Sources",action="append",nargs="+", widget='Listbox', choices=available_sources, gooey_options={'height': 300},
                       help="Select the sources which You want to process")
    args = parser.parse_args()

    try:
        todo = args.Tasks[6]
    except IndexError:
        print("Keine Entitäten ausgesucht.")
        todo = ""     

    rdv_default_schema =  config.get('Snowflake', 'rdv_schema')
    stage_default_schema = config.get('Snowflake', 'stage_schema')



    for source in args.Sources[0]:
        if 'Stage' in todo:
            stage.generate_stage(cursor,source, generated_timestamp, stage_default_schema, model_path, hashdiff_naming)
        
        if 'Hub' in todo: 
            hub.generate_hub(cursor,source, generated_timestamp, rdv_default_schema, model_path)
    
        if 'Link' in todo: 
            link.generate_link(cursor,source, generated_timestamp, rdv_default_schema, model_path)

        if 'Satellite' in todo: 
            satellite.generate_satellite(cursor, source, generated_timestamp, rdv_default_schema, model_path, hashdiff_naming)
        if 'Pit' in todo:
            pit.generate_pit(cursor,source, generated_timestamp, model_path)
            
        if 'Non Historized Satellite' in todo: 
            nh_satellite.generate_nh_satellite(cursor, source, generated_timestamp, rdv_default_schema, model_path)


if __name__ == "__main__":
    print("Starting Script.")
    start = time.time()
    main()
    end = time.time()
    print("Script ends.")
    print("Total Runtime: " + str(round(end - start, 2)) + "s")