import requests
import os

from app_settings import STAGE_URL
from helpers.helpers import load_json_file, convert_dict_keys_to_float


def get_response_for_testing(payload, override):
    """
    Gets a response from the staging endpoint for testing. If the staging endpoint is not available (e.g. hasn't been
    deployed yet), then we can pass in an override Boolean to hit a local web server.

    :param payload: json payload to be sent to our model API
    :param override: Boolean of whether or not to override hitting the staging endpoint in lieu of the local server
    :return: json response
    """
    if override:
        print(payload)
        response = requests.post('http://127.0.0.1:5000/predict', json=payload)
    else:
        response = requests.post(f'{STAGE_URL}/predict', json=payload)
    return response.json()


def _test_high_risk_category(response):
    """
    Tests if the high_risk key in the response is either 'yes' or 'no'.

    :param response: json response from the API
    :return: tuple with Boolean of pass or fail and associated message
    """
    high_risk = response.get('high_risk', 'none')
    if high_risk not in ['yes', 'no']:
        return False, 'high_risk is not either yes or no'
    else:
        return True, 'high_risk is acceptable'


def _test_high_risk_cutoff(response, config_dict):
    """
    Tests if the high_risk distinction is given to predictions above proba_cutoff.

    :param response: json response from the API
    :param config_dict: the current configuration dictionary
    :return: tuple with Boolean of pass or fail and associated message
    """
    proba_cutoff = float(config_dict.get('proba_cutoff', -1))
    prediction = float(response.get('prediction'))
    high_risk = response.get('high_risk')
    if proba_cutoff == -1:
        return False, 'proba_cutoff is not in the config'
    if prediction >= proba_cutoff:
        if high_risk == 'yes':
            return True, 'payload should be high risk and is flagged correctly'
        else:
            return False, 'payload should be flagged as high_risk but is not'
    if prediction < proba_cutoff:
        if high_risk == 'no':
            return True, 'payload should not be high risk and is flagged correctly'
        else:
            return False, 'payload should be not be flagged as high_risk but is'


def validate_config_change(config_dict, override):
    """
    Hits the model API with sample payloads and validates the responses are what we expect based on the config settings.

    :param config_dict: the current configuration dictionary
    :param override: Boolean of whether or not to override hitting the staging endpoint in lieu of the local server
    :return: tuple with Boolean if all tests passed and associated error messages if applicable
    """
    payload_1 = load_json_file(os.path.join('payloads', 'payload_1.json'))
    payload_1 = convert_dict_keys_to_float(payload_1)
    payload_2 = load_json_file(os.path.join('payloads', 'payload_2.json'))
    payload_2 = convert_dict_keys_to_float(payload_2)
    response_1 = get_response_for_testing(payload_1, override)
    response_2 = get_response_for_testing(payload_2, override)
    test_1 = _test_high_risk_category(response_1)
    test_2 = _test_high_risk_cutoff(response_1, config_dict)
    test_3 = _test_high_risk_category(response_2)
    test_4 = _test_high_risk_cutoff(response_2, config_dict)
    test_results = [test_1, test_2, test_3, test_4]
    errors = []
    messages = []
    for i in test_results:
        errors.append(i[0])
        messages.append(i[1])
    false_check = any(errors)
    if not false_check:
        false_indices = [i for i, x in enumerate(errors) if not x]
        messages = [messages[i] for i in false_indices]
    return false_check, messages
