import streamlit as st

from app_settings import SCHEMA_NAME, CONFIG_SCHEMA, S3_BUCKET_NAME
from helpers.helpers import retrieve_config, log_config_change_to_s3, validate_user_data, convert_entry_to_dict, \
    update_config_table, hit_config_refresh_endpoint
from build_tests.build_tests import validate_config_change
from utilities import streamlit_session


def accept_user_environment_selection():
    """
    Allows the user to select the environment they want to update.

    :return: streamlit checkbox
    """
    return st.selectbox(
        'Select the environment in which to make the config changes',
        ('stage', 'prod'))


def accept_user_config_changes(default):
    """
    Allows user to update the config dictionary.

    :param default: current config dictionary string
    :return: updated config dictionary string
    """
    user_input = st.text_input('Update the config key-value pairs here. Default values are the current prod values',
                               default)
    return user_input


def raise_entry_validation_error():
    """
    Raises alert that entry is not valid.

    :return: streamlit text
    """
    return st.text('provided input data is not valued')


def raise_test_value_error(message):
    """
    Raises alert that the config updates failed tests.

    :param message: error messages
    :return: streamlit text
    """
    return st.text(f'config updates failed tests: {message}')


def main():
    """
    UI config application that allows us to do the following:
    - renders the current config
    - allows the user to update the config
    - validates the entries meet certain specifications
    - if the entries are valid, pushes new config to staging
    - runs tests against the staging app
    - if the tests pass, pushed the new config to production
    - logs the config changes to S3
    """
    session = streamlit_session.get(name="", button_sent=False, entry_valid=False)
    st.title('CHURN MODEL API CONFIG SETTINGS')
    st.text('''Use this application to update the churn model API.''')
    st.text('''Prod updates are tested in the staging before being pushed to production.''')
    st.text('''-------------------------------------------------------------------------''')
    current_prod_config = retrieve_config(SCHEMA_NAME, 'prod')
    current_stage_config = retrieve_config(SCHEMA_NAME, 'stage')
    user_entry = accept_user_config_changes(current_prod_config)
    st.text('''-------------------------------------------------------------------------''')
    st.text('Current staging config')
    st.text(current_stage_config)
    st.text('''-------------------------------------------------------------------------''')
    environment_selection = accept_user_environment_selection()
    button_sent = st.button('SUBMIT CHANGES')
    if button_sent:
        session.button_sent = True
        user_entry = convert_entry_to_dict(user_entry)
        entry_valid = validate_user_data(user_entry, CONFIG_SCHEMA)
        if entry_valid:
            session.entry_valid = True
        else:
            raise_entry_validation_error()
    if session.button_sent:
        if session.entry_valid:
            st.text('new config values pass value validation!')
            st.text(f'selected environment: {environment_selection}')
            st.text(f'selected config settings: {user_entry}')
            confirm_button = st.button('CONFIRM CHANGES')
            if confirm_button:
                user_entry = convert_entry_to_dict(user_entry)
                update_config_table(user_entry, SCHEMA_NAME, 'stage_config')
                # TODO: flip to 'stage' when deploying
                hit_config_refresh_endpoint('local')
                st.text('running tests against config changes...')
                # TODO: flip to false when deploying
                passed_tests, message = validate_config_change(user_entry, True)
                if passed_tests:
                    if environment_selection == 'prod':
                        st.text('tests passed!')
                        update_config_table(user_entry, SCHEMA_NAME, 'prod_config')
                        # TODO: flip to 'prod' when deploying
                        hit_config_refresh_endpoint('local')
                else:
                    raise_test_value_error(message)
                    passed_tests = None
                st.subheader('please refresh browser to reset the page')
                log_config_change_to_s3(environment_selection, user_entry, session.entry_valid,
                                        passed_tests, S3_BUCKET_NAME)


if __name__ == "__main__":
    main()
