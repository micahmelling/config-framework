import os
import uuid
import pandas as pd
import streamlit as st
import requests
import json

from ds_helpers import aws, db
from app_settings import STAGE_URL, PROD_URL, DATABASE_SECRET


def load_json_file(path):
    """
    Loads a json file.

    :param path: path to json file
    :return: json path
    """
    with open(path, 'r') as file:
        return json.loads(file.read())


def convert_dict_keys_to_float(dictionary):
    """
    Converts dictionary keys to floats when possible.

    :param dictionary: dict
    """
    for k, v in dictionary.items():
        try:
            dictionary[k] = float(v)
        except ValueError:
            pass
    return dictionary


def log_config_change_to_s3(environment_selection, config_values, schema_validation, error_validation, bucket_name):
    """
    Logs config changes to an S3 bucket.

    :param environment_selection: which environment we are updating (stage or prod)
    :param config_values: the new config values
    :param schema_validation: results of the schema validation
    :param error_validation: results of the error validation
    :param bucket_name: name of the S3 bucket
    """
    uid = str(uuid.uuid4())
    payload = dict()
    payload['environment_selection'] = environment_selection
    payload['schema_validation'] = schema_validation
    payload['error_validation'] = error_validation
    payload['uid'] = uid
    payload['config_values'] = config_values
    with open(f'{uid}.json', 'w') as outfile:
        outfile.write(str(payload))
    aws.upload_file_to_s3(f'{uid}.json', bucket_name)
    os.remove(f'{uid}.json')


@st.cache
def set_s3_keys(secret_name):
    """
    Sets S3 keys that can interact with the S3 loggin bucket

    :param secret_name: Secrets Manager secret that contains the AWS keys
    """
    s3_keys_dict = aws.get_secrets_manager_secret(secret_name)
    os.environ['AWS_ACCESS_KEY_ID'] = s3_keys_dict.get('AWS_ACCESS_KEY_ID')
    os.environ['AWS_SECRET_ACCESS_KEY'] = s3_keys_dict.get('AWS_SECRET_ACCESS_KEY')


def retrieve_config(schema, environment):
    """
    Retrieves the config from MySQL.

    :param schema: name of the MySQL schema
    :param environment: prod or stage
    :return: dictionary of config values
    """
    if environment == 'stage':
        table_name = 'stage_config'
    elif environment == 'prod':
        table_name = 'prod_config'
    else:
        raise Exception('environment must either be stage or prod')
    query = f'''
    select config_key, config_value 
    from {schema}.{table_name}
    where meta__inserted_at = (select max(meta__inserted_at) from {schema}.{table_name})
    ;'''
    mysql_conn_dict = aws.get_secrets_manager_secret(DATABASE_SECRET)
    df = pd.read_sql(query, db.connect_to_mysql(mysql_conn_dict))
    df = df.set_index('config_key')
    df_dict = df.to_dict().get('config_value')
    return df_dict


def validate_user_data(user_data, schema):
    """
    Validates the new config values meet certain criteria.

    :param user_data: the new config values entered by the user
    :param schema: Schema object
    :return: Boolean
    """
    return schema.is_valid([user_data])


def convert_entry_to_dict(data_str):
    """
    Converts the user entry from a dictionary string to a dictionary.

    :param data_str: dictionary string
    :return: dictionary
    """
    data_dict = data_str.replace("'", '"')
    data_dict = json.loads(data_dict)
    return data_dict


def update_config_table(data_dict, schema_name, table_name):
    """
    Updates the config tables in MySQL.

    :param data_dict: dictionary of config keys and values
    :param schema_name: name of the schema
    :param table_name: name of the table
    """
    main_df = pd.DataFrame()
    for key, value in data_dict.items():
        temp_df = pd.DataFrame({'config_key': [key], 'config_value': [value]})
        main_df = main_df.append(temp_df)
    mysql_conn_dict = aws.get_secrets_manager_secret(DATABASE_SECRET)
    db.write_dataframe_to_database(main_df, schema_name, table_name, db.connect_to_mysql(mysql_conn_dict))


def hit_config_refresh_endpoint(environment, refresh_times=1):
    """
    Hits the application's config-refresh endpoint to update the config in the application.

    :param environment: stage or prod
    :param refresh_times: number of times to hit the refresh endpoint, which might need to be more than 1 if we are
    running multiple tasks behind a load balance on AWS
    """
    st.text('refreshing config...')
    if environment == 'local':
        url = 'http://127.0.0.1:5000/config-refresh'
    elif environment == 'stage':
        url = f'{STAGE_URL}/config-refresh'
    elif environment == 'prod':
        url = f'{PROD_URL}/config-refresh'
    else:
        raise ValueError('environment must be stage or prod')
    for i in range(refresh_times):
        requests.get(url)
    st.text(f'config refreshed for {environment}!')
