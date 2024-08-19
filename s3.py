import logging
from datetime import datetime
from urllib.parse import urlparse

import httpx
import boto3
from botocore.client import Config, BaseClient
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError


class S3Client:
    def __init__(self, region, bucket, endpoint_url, public_url, access_key_id, secret_access_key):
        self.region = region
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.public_url = public_url
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key

        self.client: BaseClient = boto3.client(
            's3',
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            endpoint_url=self.endpoint_url,
            region_name=self.region,
            config=Config(signature_version='s3v4')
        )

        self.validate()

    def validate(self):
        content = f"CREATE_BY: grafana-tool_reporter\nCREATE_TS: {datetime.now().timestamp()}"
        try:
            logging.info("S3配置验证：上传验证中...")
            self.client.put_object(Bucket=self.bucket, Key='.s3_config_validate', Body=content.encode())
            logging.info("S3配置验证：上传成功")

            # 如果存在 public_url，则尝试使用 public_url 下载
            if self.public_url:
                try:
                    parsed_url = urlparse(self.public_url)
                    response = httpx.get(f"{parsed_url.scheme}://{parsed_url.netloc}/{self.bucket}/.s3_config_validate")
                    response.raise_for_status()
                    downloaded_content = response.text
                    if content.strip() == downloaded_content.strip():
                        logging.warning("S3配置验证：public_url 验证成功。")
                    else:
                        logging.error(f"S3配置验证失败：上传与读取文件内容不匹配。")
                        raise Exception("S3配置验证失败：上传与读取文件内容不匹配。")
                except Exception as e:
                    logging.debug(e)
                    logging.warning("S3配置验证：配置中的 public_url 不可用，将使用预签名链接返回对象url，预签名链接将在 1 小时后过期。")
                    self.public_url = None
            else:
                logging.warning("S3配置验证：未配置 public_url ，将使用预签名链接返回对象url，预签名链接将在 1 小时后过期。")

            if self.public_url is None:
                logging.info("S3配置验证：读取验证中...")
                response = self.client.get_object(Bucket=self.bucket, Key='.s3_config_validate')
                downloaded_content = response['Body'].read().decode()
                if content.strip() == downloaded_content.strip():
                    logging.info(f"S3配置验证：读取成功")
                else:
                    logging.error(f"S3配置验证失败：上传与读取文件内容不匹配。")
                    raise Exception("S3配置验证失败：上传与读取文件内容不匹配。")

        except NoCredentialsError:
            logging.error("S3配置验证失败：缺少有效凭证。")
            raise Exception("S3配置验证失败：缺少有效凭证。")
        except PartialCredentialsError:
            logging.error("S3配置验证失败：凭证不完整。")
            raise Exception("S3配置验证失败：凭证不完整。")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                logging.error("S3配置验证失败：桶不存在。请检查桶名称是否正确。")
                raise Exception("S3配置验证失败：桶不存在。请检查桶名称是否正确。")
            elif error_code == 'AccessDenied':
                logging.error("S3配置验证失败：访问被拒绝。请检查您的访问权限。")
                raise Exception("S3配置验证失败：访问被拒绝。请检查您的访问权限。")
            else:
                logging.error(f"S3配置验证失败：{e.response['Error']['Message']}")
                raise Exception(f"S3配置验证失败：{e.response['Error']['Message']}")
        except Exception as e:
            logging.error(f"S3配置验证失败：{str(e)}")
            raise Exception(f"S3配置验证失败：{str(e)}")

    def upload(self, filepath):
        """
        :param filepath: 要上传的文件
        :return: True 如果上传成功，否则 False
        """
        try:
            self.client.upload_file(filepath, self.bucket, filepath)

            object_url = None
            # 如果存在 public_url，则尝试拼接公开访问链接
            if self.public_url:
                parsed_url = urlparse(self.public_url)
                object_url = f"{parsed_url.scheme}://{parsed_url.netloc}/{self.bucket}/{filepath}"
            # 如果 public_url 不存在或无法拼接链接，则生成预签名链接
            if not object_url:
                object_url = self.create_presigned_url(filepath)

            return object_url
        except FileNotFoundError:
            logging.error("文件上传错误: 文件不存在")
            return None
        except Exception as e:
            logging.error(f"文件上传错误: {e}")
            return None

    def create_presigned_url(self, object_name, expiration=3600):
        """Generate a presigned URL to share an S3 object
        :param object_name:
        :param expiration: Time in seconds for the presigned URL to remain valid
        :return: Presigned URL as string. If error, returns None.
        """
        try:
            response = self.client.generate_presigned_url('get_object', Params={'Bucket': self.bucket, 'Key': object_name}, ExpiresIn=expiration)
        except ClientError as e:
            logging.error(e)
            return None
        return response
