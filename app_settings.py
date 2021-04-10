from schema import Schema, And, Use


AWS_KEYS_SECRET = 'churn-api-s3-keys'
DATABASE_SECRET = 'churn-model-mysql'
S3_BUCKET_NAME = 'churn-model-data-science-logs'
SCHEMA_NAME = 'churn_model'
STAGE_URL = 'stage_url'
PROD_URL = 'prod_url'

CONFIG_SCHEMA = Schema([{
    'proba_cutoff':  And(Use(float), lambda n: 0.09 <= n <= 0.99)
}])
