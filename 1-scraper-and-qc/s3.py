import os
import json
import boto3
import tempfile
import requests
import mimetypes
import polars as pl
import time
from pathlib import Path
from dotenv import load_dotenv
from cloudpathlib import S3Path
from urllib.parse import urlparse
from typing import Optional, Tuple
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from botocore.exceptions import ClientError

# Load environment variables
load_dotenv()


class S3Client:
    def __init__(self):
        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
            region_name=os.getenv("AWS_REGION"),
        )

    def read_all_json(self, bucket: str, prefix: str = "") -> list:
        json_files = [key for key in self.list_objects(bucket, prefix) if key.endswith(".json")]
        all_data = []

        for key in json_files:
            print(f"Reading: s3://{bucket}/{key}")
            data = self.read_json(f"s3://{bucket}/{key}")

            # Append the data
            if isinstance(data, list):
                all_data.extend(data)
            else:
                all_data.append(data)

        return all_data

    
    def count_files(self, bucket: str, prefix: str = "", ignore_folder_keys: bool = True) -> int:
        """
        Count S3 objects under `prefix` in `bucket`.

        Parameters
        ----------
        bucket : str
            Name of the S3 bucket.
        prefix : str, optional
            Key prefix ("folder/like/path/"). Can be "" for whole bucket.
        ignore_folder_keys : bool, optional
            If True, skip keys that end with "/" (common placeholder "folder" objects).

        Returns
        -------
        int
            Number of objects counted.
        """
        paginator = self.s3.get_paginator("list_objects_v2")
        total = 0

        try:
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if ignore_folder_keys and key.endswith("/"):
                        continue
                    total += 1
        except ClientError as e:
            # Bubble up or handle as you prefer
            raise RuntimeError(f"Error listing objects: {e}") from e

        return total

    def list_buckets(self):
        response = self.s3.list_buckets()
        return [bucket["Name"] for bucket in response.get("Buckets", [])]

    def list_objects(self, bucket: str, prefix: str = ""):
        response = self.s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        contents = response.get("Contents", [])
        return [obj["Key"] for obj in contents]

    def download_file(self, bucket: str, key: str, local_path: str):
        self.s3.download_file(bucket, key, local_path)

    def upload_file(self, local_path: str, bucket: str, key: str):
        self.s3.upload_file(local_path, bucket, key)

    def read_csv(self, bucket: str, key: str, **kwargs) -> pl.DataFrame:
        s3_uri = f"s3://{bucket}/{key}"
        return pl.read_csv(s3_uri, **kwargs)

    def read_parquet(self, bucket: str, key: str, **kwargs) -> pl.DataFrame:
        s3_uri = f"s3://{bucket}/{key}"
        return pl.read_parquet(s3_uri, **kwargs)

    def read_json(self, s3_path: str) -> dict:
        parsed = urlparse(s3_path)
        if parsed.scheme != "s3":
            raise ValueError("Path must start with s3://")

        bucket = parsed.netloc
        key = parsed.path.lstrip("/")  # remove leading slash

        response = self.s3.get_object(Bucket=bucket, Key=key)
        return json.loads(response["Body"].read())

    def _detect_file_extension(self, url: str, content_type: str = None) -> str:
        """
        Detect file extension from URL or content type
        """
        # First try to get extension from URL
        parsed_url = urlparse(url)
        path = Path(parsed_url.path)
        
        if path.suffix:
            return path.suffix.lower()
        
        # If no extension in URL, try to get it from content type
        if content_type:
            extension = mimetypes.guess_extension(content_type)
            if extension:
                return extension.lower()
        
        # Default fallback
        return ".bin"

    def _file_exists_in_s3(self, bucket: str, key: str) -> bool:
        """
        Check if a file exists in S3
        """
        try:
            self.s3.head_object(Bucket=bucket, Key=key)
            return True
        except self.s3.exceptions.NoSuchKey:
            return False
        except Exception:
            return False

    def _create_robust_session(self, timeout: int = 30) -> requests.Session:
        """
        Create a requests session with retry strategy and proper headers
        """
        session = requests.Session()
        
        # Set up retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set headers to mimic a real browser
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        return session

    def upload_media(
        self, 
        media_url: str, 
        bucket: str, 
        s3_prefix: str, 
        filename: str,
        timeout: int = 30,
        chunk_size: int = 8192,
        skip_if_exists: bool = True,
        max_retries: int = 3,
        retry_delay: int = 2
    ) -> Tuple[str, str, bool]:
        """
        Upload media file from URL to S3 with robust error handling
        
        Args:
            media_url: URL of the media file to download
            bucket: S3 bucket name
            s3_prefix: S3 prefix/folder path
            filename: Base filename (without extension)
            timeout: Request timeout in seconds
            chunk_size: Download chunk size in bytes
            skip_if_exists: Skip upload if file already exists in S3
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            Tuple of (s3_key, final_filename, was_uploaded)
            was_uploaded: True if file was uploaded, False if skipped, None if failed
        """
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                # Create robust session
                session = self._create_robust_session(timeout)
                
                # Make a HEAD request first to get content type and size
                try:
                    head_response = session.head(media_url, timeout=timeout, allow_redirects=True)
                    content_type = head_response.headers.get('content-type', '')
                except requests.exceptions.RequestException:
                    # If HEAD fails, we'll get content type from GET request
                    content_type = ''
                
                # Detect file extension
                extension = self._detect_file_extension(media_url, content_type)
                
                # Create final filename with extension
                final_filename = f"{filename}{extension}"
                
                # Create S3 key
                s3_key = f"{s3_prefix.rstrip('/')}/{final_filename}"
                
                # Check if file already exists
                if skip_if_exists and self._file_exists_in_s3(bucket, s3_key):
                    print(f"File already exists in S3: {s3_key} - Skipping upload")
                    return s3_key, final_filename, False
                
                # Stream download and upload to S3
                with session.get(media_url, stream=True, timeout=timeout, allow_redirects=True) as response:
                    response.raise_for_status()
                    
                    # Get content type if not available from HEAD request
                    if not content_type:
                        content_type = response.headers.get('content-type', 'application/octet-stream')
                    
                    # Use upload_fileobj for streaming upload
                    self.s3.upload_fileobj(
                        response.raw,
                        bucket,
                        s3_key,
                        ExtraArgs={'ContentType': content_type}
                    )
                
                print(f"Successfully uploaded to S3: {s3_key}")
                return s3_key, final_filename, True
                
            except requests.exceptions.RequestException as e:
                last_exception = e
                print(f"Network error on attempt {attempt + 1}/{max_retries}: {str(e)}")
                if attempt < max_retries - 1:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                else:
                    print(f"Failed to download after {max_retries} attempts")
                    return None, None, None
                    
            except Exception as e:
                last_exception = e
                print(f"Upload error on attempt {attempt + 1}/{max_retries}: {str(e)}")
                if attempt < max_retries - 1:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                else:
                    print(f"Failed to upload after {max_retries} attempts")
                    return None, None, None
        
        # If we get here, all retries failed
        raise Exception(f"Failed to upload media after {max_retries} attempts. Last error: {str(last_exception)}")
    
    def put_json(self, bucket: str, key: str, data):
        self.s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(data, ensure_ascii=False, indent=2),
            ContentType="application/json"
        )

    def upload_media_with_temp(
        self, 
        media_url: str, 
        bucket: str, 
        s3_prefix: str, 
        filename: str,
        timeout: int = 30,
        skip_if_exists: bool = True
    ) -> Tuple[str, str, bool]:
        """
        Alternative method: Download to temp file first, then upload to S3
        Use this if streaming upload doesn't work or you need to process the file
        
        Args:
            media_url: URL of the media file to download
            bucket: S3 bucket name
            s3_prefix: S3 prefix/folder path
            filename: Base filename (without extension)
            timeout: Request timeout in seconds
            skip_if_exists: Skip upload if file already exists in S3
            
        Returns:
            Tuple of (s3_key, final_filename, was_uploaded)
            was_uploaded: True if file was uploaded, False if skipped
        """
        try:
            # Make a HEAD request to get content type
            head_response = requests.head(media_url, timeout=timeout)
            content_type = head_response.headers.get('content-type', '')
            
            # Detect file extension
            extension = self._detect_file_extension(media_url, content_type)
            final_filename = f"{filename}{extension}"
            s3_key = f"{s3_prefix.rstrip('/')}/{final_filename}"
            
            # Check if file already exists
            if skip_if_exists and self._file_exists_in_s3(bucket, s3_key):
                print(f"File already exists in S3: {s3_key} - Skipping upload")
                return s3_key, final_filename, False
            
            # Download to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
                temp_path = temp_file.name
                
                with requests.get(media_url, stream=True, timeout=timeout) as response:
                    response.raise_for_status()
                    
                    # Update content type if not available from HEAD request
                    if not content_type:
                        content_type = response.headers.get('content-type', 'application/octet-stream')
                    
                    # Write to temp file
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            temp_file.write(chunk)
            
            try:
                # Upload to S3 with content type
                self.s3.upload_file(
                    temp_path,
                    bucket,
                    s3_key,
                    ExtraArgs={'ContentType': content_type}
                )
                
                print(f"Successfully uploaded to S3: {s3_key}")
                return s3_key, final_filename, True
                
            finally:
                # Clean up temp file
                os.unlink(temp_path)
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to download media from URL: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to upload media to S3: {str(e)}")